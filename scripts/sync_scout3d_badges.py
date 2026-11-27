"""把 SCOUT 3D 官方徽章庫（`playerkousas-rgb/SCOUT3D` 的 `public/badges/`）同步入本 repo。

點解要有呢個 script：
  makemovie 出片時**只讀本地章圖**（`assets/scout3d/badges/`），
  咁其他人 clone 落嚟即刻可以用，唔需要上網、唔需要另裝 SCOUT3D。

用法：
    python scripts/sync_scout3d_badges.py
        由 GitHub 拉最新 SCOUT3D → 複製缺檔／更新過的 PNG → 重新產生 manifest.json

    python scripts/sync_scout3d_badges.py --from-dir D:\\SCOUT3D\\public\\badges
        用你本機已有的 SCOUT3D（唔上網）

    python scripts/sync_scout3d_badges.py --check
        只檢查有冇差異，唔寫入（CI 用；有差異 exit 1）

會寫入：
    assets/scout3d/badges/**.png        章圖
    assets/scout3d/badges/manifest.json 路徑 + bytes + sha256 + 來源 commit
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import scout3d_badges as B  # noqa: E402

DEFAULT_REPO = "https://github.com/playerkousas-rgb/SCOUT3D.git"
DEFAULT_SUBDIR = "public/badges"


def _clone_sparse(repo: str, subdir: str) -> tuple[Path, str]:
    tmp = Path(tempfile.mkdtemp(prefix="scout3d_badges_"))
    print(f"[sync-badges] 由 {repo} 取 {subdir} …")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repo, str(tmp)],
        check=True,
    )
    subprocess.run(["git", "sparse-checkout", "set", subdir], cwd=tmp, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
    ).stdout.strip()
    return tmp / subdir, commit


def _sync(src_dir: Path, *, check_only: bool) -> int:
    src_files = {p.relative_to(src_dir).as_posix(): p for p in src_dir.rglob("*.png")}
    added: list[str] = []
    updated: list[str] = []
    for rel, path in sorted(src_files.items()):
        dst = B.BADGE_DIR / rel
        if not dst.exists():
            added.append(rel)
        elif dst.stat().st_size != path.stat().st_size or B._sha256(dst) != B._sha256(path):
            updated.append(rel)

    local_only = sorted(
        {p.relative_to(B.BADGE_DIR).as_posix() for p in B.BADGE_DIR.rglob("*.png")} - set(src_files)
    )

    print(
        f"[sync-badges] SCOUT3D {len(src_files)} 個章 · 新檔 {len(added)} · 有更新 {len(updated)}"
        f" · 本地獨有 {len(local_only)}"
    )
    for rel in added[:10]:
        print(f"  + {rel}")
    if len(added) > 10:
        print(f"  … 另外 {len(added) - 10} 個新檔")
    for rel in updated[:10]:
        print(f"  ~ {rel}")
    for rel in local_only[:10]:
        print(f"  ? 本地有但 SCOUT3D 冇（保留，唔會刪）：{rel}")

    if check_only:
        return 1 if (added or updated) else 0
    if not added and not updated:
        print("[sync-badges] 已經係最新，冇需要更新。")
        return 0

    for rel, path in sorted(src_files.items()):
        dst = B.BADGE_DIR / rel
        if rel in added or rel in updated:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="同步 SCOUT3D 官方徽章庫（只讀本地、離線可用）")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="SCOUT3D git repo")
    ap.add_argument("--subdir", default=DEFAULT_SUBDIR, help="徽章目錄（repo 內）")
    ap.add_argument("--from-dir", help="改用本機已 clone 的 public/badges 目錄（唔上網）")
    ap.add_argument("--check", action="store_true", help="只檢查差異，唔寫入檔案")
    args = ap.parse_args(argv)

    tmp_root: Path | None = None
    if args.from_dir:
        src_dir = Path(args.from_dir).expanduser().resolve()
        commit = ""
        if not src_dir.is_dir():
            print(f"[sync-badges] ✗ 目錄唔存在：{src_dir}")
            return 2
    else:
        try:
            src_dir, commit = _clone_sparse(args.repo, args.subdir)
            tmp_root = src_dir.parent.parent
        except Exception as exc:
            print(f"[sync-badges] ✗ 拉唔到 SCOUT3D：{exc}")
            print("            你可以用本機已有的章庫：--from-dir D:\\SCOUT3D\\public\\badges")
            return 2

    old = B.load_manifest()
    rc = _sync(src_dir, check_only=args.check)
    if args.check:
        if tmp_root:
            shutil.rmtree(tmp_root, ignore_errors=True)
        return rc

    manifest = B.build_manifest(
        "playerkousas-rgb/SCOUT3D",
        args.subdir,
        commit or old.get("source_commit") or "unknown",
    )
    B.MANIFEST_PATH.write_text(
        __import__("json").dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"[sync-badges] ✓ manifest 已更新：{manifest['count']} 個章（commit {manifest['source_commit'][:8]}）")
    print("[sync-badges] 跟住可以跑：python src/check_badge_assets.py")
    if tmp_root:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
