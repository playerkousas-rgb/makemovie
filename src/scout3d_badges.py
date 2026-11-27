"""SCOUT 3D 徽章資產（`assets/scout3d/badges/*.png`）解析 + 驗證。

v3.5 起：
· SCOUT 3D 官方**全部**徽章（`public/badges/` 549 個 PNG）已經鏡像入本 repo，
  clone 落嚟就有，唔需要上網、唔需要另裝 SCOUT3D。
· render 時**只讀本地檔**，唔會再即場下載（以前下載失敗會寫入錯誤頁，
  之後每次 render 都 `PIL.UnidentifiedImageError` 炸片）。
· 缺章／壞章 → 出片前即刻報錯，列出缺咩同喺邊度補，唔會靜靜雞出咗條缺章嘅片。

對外用：
    from scout3d_badges import preflight_spec_badges, BadgeAssetError
    preflight_spec_badges(spec)          # 有問題就 raise BadgeAssetError

CLI：
    python src/check_badge_assets.py                 # 檢查本地章庫 + manifest
    python src/check_badge_assets.py --spec foo.json # 檢查某個 spec 用到嘅章
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BADGE_DIR = REPO_ROOT / "assets" / "scout3d" / "badges"
MANIFEST_PATH = BADGE_DIR / "manifest.json"
RIG_JSON_PATH = REPO_ROOT / "assets" / "scout3d" / "scout3d_rig_data.json"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class BadgeAssetError(RuntimeError):
    """章圖缺失或者損壞（唔會出片）。"""


# ----------------------------------------------------------------------
# 路徑
# ----------------------------------------------------------------------
def normalize_rel(rel: Any) -> str:
    """`badges/awards/x.png` / `/awards/x.png` / `awards/x.png` → `awards/x.png`。"""
    clean = str(rel or "").strip().replace("\\", "/").lstrip("/")
    if clean.startswith("./"):
        clean = clean[2:]
    if clean.startswith("badges/"):
        clean = clean[len("badges/"):]
    return clean


def badge_path(rel: Any) -> Path:
    return BADGE_DIR / normalize_rel(rel)


def file_is_png(path: Path, *, min_bytes: int = 24) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < min_bytes:
            return False
        with path.open("rb") as fh:
            return fh.read(8) == PNG_MAGIC
    except Exception:
        return False


# ----------------------------------------------------------------------
# 從 spec / rig data 收集用到的章
# ----------------------------------------------------------------------
def _walk_arts(obj: Any, out: Set[str]) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ("art", "artPath", "badgeArt", "file", "tex") and isinstance(val, str):
                # dyn 類（__dyn_troop__ 等）係程式即時畫，唔係檔案
                if val and not val.startswith("__"):
                    rel = normalize_rel(val)
                    if rel.lower().endswith(".png"):
                        out.add(rel)
            _walk_arts(val, out)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _walk_arts(item, out)


def rig_badge_arts() -> Set[str]:
    """`scout3d_rig_data.json` 內所有會用到的章圖。"""
    out: Set[str] = set()
    try:
        data = json.loads(RIG_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return out
    _walk_arts(data, out)
    return out


def spec_badge_arts(spec: Dict[str, Any]) -> Set[str]:
    """一個 episode spec 內（角色陣容 / s3d 穿搭碼 / 鏡頭層）會用到的章圖。"""
    out: Set[str] = set()
    if not isinstance(spec, dict):
        return out
    _walk_arts(spec.get("s3d_custom"), out)
    for cast_key in ("characters", "cast"):
        _walk_arts(spec.get(cast_key), out)
    for sh in spec.get("shots") or []:
        if isinstance(sh, dict):
            _walk_arts(sh.get("cast"), out)
            _walk_arts(sh.get("s3d_custom"), out)
    return out


# ----------------------------------------------------------------------
# 驗證
# ----------------------------------------------------------------------
def check_arts(arts: Iterable[str]) -> Tuple[List[str], List[str]]:
    """回傳 (缺失清單, 損壞清單)，兩個都係相對路徑。"""
    missing: List[str] = []
    broken: List[str] = []
    for rel in sorted(set(normalize_rel(a) for a in arts if a)):
        p = BADGE_DIR / rel
        if not p.is_file():
            missing.append(rel)
        elif not file_is_png(p):
            broken.append(rel)
    return missing, broken


def _format_problem(title: str, items: List[str], hint: str) -> str:
    lines = [f"[scout3d-runner] ✗ {title}"]
    for rel in items:
        lines.append(f"  {rel}   ← 期望位置 {BADGE_DIR / rel}")
    lines.append(f"  {hint}")
    return "\n".join(lines)


def preflight_spec_badges(spec: Dict[str, Any]) -> None:
    """出片前檢查：spec 用到嘅章全部要喺本地，而且係正常 PNG。"""
    arts = spec_badge_arts(spec) | rig_badge_arts()
    missing, broken = check_arts(arts)
    if missing:
        raise BadgeAssetError(
            _format_problem(
                f"缺失 {len(missing)} 個徽章圖（唔會出片）",
                missing,
                "解決：git checkout -- assets/scout3d/badges（章庫已經內置，缺檔多數係誤刪或 clone 未完成）",
            )
        )
    if broken:
        raise BadgeAssetError(
            _format_problem(
                f"{len(broken)} 個徽章圖損壞（唔係正常 PNG，唔會出片）",
                broken,
                "解決：git checkout -- assets/scout3d/badges  然後跑 python src/check_badge_assets.py",
            )
        )


def load_manifest() -> Dict[str, Any]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def verify_manifest(deep: bool = True) -> List[str]:
    """核對 manifest：缺檔、多餘檔、hash 不符。回傳問題清單（空 = 全部正常）。"""
    manifest = load_manifest()
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    problems: List[str] = []
    if not files:
        return ["manifest.json 唔存在或者係空（跑 python src/sync_scout3d_badges.py 重新產生）"]

    on_disk = {normalize_rel(str(p.relative_to(BADGE_DIR))) for p in BADGE_DIR.rglob("*.png")}
    for rel, meta in sorted(files.items()):
        p = BADGE_DIR / rel
        if not p.is_file():
            problems.append(f"缺檔：{rel}")
            continue
        size = p.stat().st_size
        expect = (meta or {}).get("bytes")
        if isinstance(expect, int) and size != expect:
            problems.append(f"大小不符：{rel}（{size} != {expect}）")
            continue
        if deep:
            want = (meta or {}).get("sha256")
            if want and _sha256(p) != want:
                problems.append(f"內容不符（hash）：{rel}")
    for rel in sorted(on_disk - set(files)):
        problems.append(f"多餘檔（manifest 冇記錄）：{rel}")
    return problems


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(source_repo: str, source_path: str, source_commit: str) -> Dict[str, Any]:
    files: Dict[str, Dict[str, Any]] = {}
    for p in sorted(BADGE_DIR.rglob("*.png")):
        rel = normalize_rel(str(p.relative_to(BADGE_DIR)))
        files[rel] = {"bytes": p.stat().st_size, "sha256": _sha256(p)}
    return {
        "source_repo": source_repo,
        "source_path": source_path,
        "source_commit": source_commit,
        "count": len(files),
        "note": "SCOUT 3D 官方徽章完整鏡像；render 只讀本地，唔會上網。",
        "files": files,
    }
