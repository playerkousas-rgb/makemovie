"""徽章資產檢查工具（v3.5）。

用法：
    python src/check_badge_assets.py
        檢查內置章庫：manifest 對唔對、有冇缺檔／多餘檔／壞 PNG。

    python src/check_badge_assets.py --spec episodes/story_example.json
    python src/check_badge_assets.py --b64 z_eJzF...
        檢查某個 spec 用到嘅章（連 rig data 用到嘅一齊驗）。

    python src/check_badge_assets.py --refresh-manifest
        重新產生 assets/scout3d/badges/manifest.json（改過章庫之後用）。

    python src/check_badge_assets.py --deep
        連 sha256 都逐個檔案重算（慢少少，CI 用）。

任何問題都會以 exit code 1 結束，方便放落 CI。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import scout3d_badges as B  # noqa: E402


def _print_header() -> None:
    manifest = B.load_manifest()
    print(
        f"[check-badge-assets] 章庫：{B.BADGE_DIR}\n"
        f"                    內置 {len(list(B.BADGE_DIR.rglob('*.png')))} 個 PNG"
        f" · 來源 {manifest.get('source_repo') or '（未記錄）'}@{(manifest.get('source_commit') or '')[:8]}"
    )


def _check_local(deep: bool) -> list[str]:
    problems = B.verify_manifest(deep=deep)
    # 任何非 PNG 的檔案（例如以前「下載失敗」寫入嘅錯誤頁）
    for p in sorted(B.BADGE_DIR.rglob("*")):
        if p.is_file() and p.suffix.lower() == ".png" and not B.file_is_png(p):
            msg = f"壞 PNG（唔係正常圖片）：{B.normalize_rel(str(p.relative_to(B.BADGE_DIR)))}"
            if msg not in problems:
                problems.append(msg)
    return problems


def _check_spec(spec: dict) -> list[str]:
    arts = B.spec_badge_arts(spec) | B.rig_badge_arts()
    missing, broken = B.check_arts(arts)
    problems: list[str] = []
    for rel in missing:
        problems.append(f"spec 要用但缺檔：{rel}")
    for rel in broken:
        problems.append(f"spec 要用但檔案損壞：{rel}")
    print(f"[check-badge-assets] spec 用到 {len(arts)} 個章（含 rig 內建）→ 缺 {len(missing)}、壞 {len(broken)}")
    return problems


def _refresh_manifest() -> int:
    old = B.load_manifest()
    manifest = B.build_manifest(
        old.get("source_repo") or "playerkousas-rgb/SCOUT3D",
        old.get("source_path") or "public/badges",
        old.get("source_commit") or "unknown",
    )
    B.MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[check-badge-assets] manifest 已更新：{manifest['count']} 個章 → {B.MANIFEST_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="檢查 SCOUT 3D 徽章資產")
    ap.add_argument("--spec", help="episode spec JSON 檔")
    ap.add_argument("--b64", help="episode spec 嘅 --b64 短碼（z_ / eJ 開頭）")
    ap.add_argument("--deep", action="store_true", help="連 sha256 都驗（預設會驗，--deep 只影響提示）")
    ap.add_argument("--refresh-manifest", action="store_true", help="重新產生 manifest.json")
    ap.add_argument("--quiet", action="store_true", help="只印問題")
    args = ap.parse_args(argv)

    if args.refresh_manifest:
        return _refresh_manifest()

    if not args.quiet:
        _print_header()

    problems = _check_local(deep=True)

    spec = None
    if args.spec:
        try:
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[check-badge-assets] ✗ 讀唔到 spec：{exc}")
            return 1
    elif args.b64:
        try:
            from scout3d_runner import decode_b64_spec

            spec = decode_b64_spec(args.b64)
        except Exception as exc:
            print(f"[check-badge-assets] ✗ 解唔到 --b64：{exc}")
            return 1
    if isinstance(spec, dict):
        problems.extend(_check_spec(spec))

    if problems:
        print(f"\n[check-badge-assets] ✗ 發現 {len(problems)} 個問題：")
        for line in problems:
            print(f"  · {line}")
        print(
            "\n修復：git checkout -- assets/scout3d/badges"
            "\n      （若果係想更新章庫：python src/sync_scout3d_badges.py）"
        )
        return 1

    if not args.quiet:
        print("[check-badge-assets] ✓ 章庫完整，全部係正常 PNG，manifest 對得上。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
