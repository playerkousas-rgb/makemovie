SUBTITLE_LINE = "最後一隻，係我嘅。"
STYLE = "crayon"

"""Tea Egg OpusCar Project — Code Animation Pipeline (Treatment 1).
- Edit Line 1 `SUBTITLE_LINE` to swap dialogue instantly (<2s) via clean-plate cache without re-rendering!
- Edit Line 2 `STYLE` ("crayon" or "pixel") or pass `--style both` to render Version A / Version B.
"""

import argparse
import glob
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

from PIL import Image
import imageio_ffmpeg

# Ensure `src/` modules resolve cleanly whether invoked as `python3 src/main.py` or `python3 -m src.main`
SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from audio import synthesize_audio
from qa_review import QAResult, build_dual_style_comparison, export_thumbnails_and_qa
from scene import render_clean_frame
from spec_loader import SpecConfig, load_specs
from subtitle import apply_subtitle_overlay


def _compute_base_plate_hash(style: str) -> str:
    """Hash all scene/style/spec source files (EXCLUDING SUBTITLE_LINE in main.py!)."""
    h = hashlib.sha256()
    h.update(f"style={style}\n".encode("utf-8"))
    tracked_py = ["spec_loader.py", "camera.py", "style_backends.py", "character.py", "scene.py"]
    for fname in tracked_py:
        h.update(fname.encode("utf-8"))
        h.update((SRC_DIR / fname).read_bytes())
    for sp in sorted(glob.glob(str(REPO_ROOT / "specs" / "*" / "*.md"))):
        # Exclude 08-typography so typography tweaks don't invalidate base plates unnecessarily
        if "08-typography" not in sp:
            h.update(Path(sp).read_bytes())
    return h.hexdigest()[:16]


_WORKER_CFG: SpecConfig | None = None
_WORKER_STYLE: str = "crayon"


def _init_worker(style: str) -> None:
    global _WORKER_CFG, _WORKER_STYLE
    _WORKER_STYLE = style
    _WORKER_CFG = load_specs()


def _render_single_plate_task(args: Tuple[int, str]) -> int:
    frame_idx, out_png = args
    assert _WORKER_CFG is not None
    img = render_clean_frame(frame_idx, _WORKER_STYLE, _WORKER_CFG)
    # Save lossless PNG to clean-plate cache
    img.save(out_png, format="PNG", compress_level=1)
    return frame_idx


def get_or_render_clean_plates(style: str, cfg: SpecConfig, force: bool = False) -> Tuple[List[Image.Image], bool]:
    """Load cached textless base frames if scene code/specs unchanged; otherwise render & cache."""
    plate_dir = REPO_ROOT / ".cache" / "clean_plates" / style
    plate_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = plate_dir / "manifest.json"
    expected_hash = _compute_base_plate_hash(style)

    cache_hit = False
    if not force and manifest_path.exists():
        try:
            meta = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                meta.get("hash") == expected_hash
                and meta.get("total_frames") == cfg.total_frames
                and all((plate_dir / f"plate_{i:03d}.png").exists() for i in range(cfg.total_frames))
            ):
                cache_hit = True
        except Exception:
            cache_hit = False

    if cache_hit:
        print(f"[{style}] CACHE HIT (hash={expected_hash}): Reusing {cfg.total_frames} clean base frames (0 scene re-renders)!")
    else:
        t0 = time.time()
        workers = min(max(1, (os.cpu_count() or 2)), 8)
        print(f"[{style}] Rendering {cfg.total_frames} clean base frames @ {cfg.width}x{cfg.height} ({cfg.fps}fps) using {workers} workers...")
        tasks = [(i, str(plate_dir / f"plate_{i:03d}.png")) for i in range(cfg.total_frames)]
        if workers > 1:
            ctx = mp.get_context("spawn")
            with ctx.Pool(processes=workers, initializer=_init_worker, initargs=(style,)) as pool:
                for done_i, _ in enumerate(pool.imap_unordered(_render_single_plate_task, tasks, chunksize=6), 1):
                    if done_i % 48 == 0 or done_i == cfg.total_frames:
                        print(f"  [{style}] {done_i}/{cfg.total_frames} base frames rendered...")
        else:
            _init_worker(style)
            for t_arg in tasks:
                _render_single_plate_task(t_arg)

        manifest_path.write_text(
            json.dumps({"hash": expected_hash, "total_frames": cfg.total_frames, "style": style}, indent=2),
            encoding="utf-8",
        )
        print(f"[{style}] Base render finished in {time.time() - t0:.2f}s.")

    frames: List[Image.Image] = []
    for i in range(cfg.total_frames):
        with Image.open(plate_dir / f"plate_{i:03d}.png") as im:
            frames.append(im.convert("RGB"))
    return frames, cache_hit


def encode_mp4(frames: List[Image.Image], wav_path: Path, out_mp4: Path, cfg: SpecConfig) -> None:
    """Encode 192 RGB frames + stereo WAV to H.264 yuv420p MP4 via bundled ffmpeg."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{cfg.width}x{cfg.height}",
        "-pix_fmt", "rgb24",
        "-r", str(cfg.fps),
        "-i", "-",
        "-i", str(wav_path),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    for im in frames:
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    stderr_bytes = proc.stderr.read() if proc.stderr else b""
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg failed (exit {ret}): {stderr_bytes.decode('utf-8', errors='replace')}")


def render_pipeline(
    style: str,
    subtitle_line: str,
    cfg: SpecConfig,
    force: bool = False,
    skip_thumbnails: bool = False,
) -> Tuple[Path, List[Image.Image], QAResult | None]:
    t_start = time.time()
    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_frames, cache_hit = get_or_render_clean_plates(style, cfg, force=force)

    # Post-process code subtitle overlay ONLY on Shot 3 [132..191]
    t_sub = time.time()
    final_frames: List[Image.Image] = [
        apply_subtitle_overlay(im, idx, subtitle_line, style, cfg)
        for idx, im in enumerate(clean_frames)
    ]
    print(f"[{style}] Subtitle overlay ('{subtitle_line}') applied in {time.time() - t_sub:.2f}s.")

    # Synthesize or reuse cached procedural audio track
    wav_path = REPO_ROOT / ".cache" / "audio" / f"bgm_{style}.wav"
    if force or not wav_path.exists():
        synthesize_audio(style, wav_path, duration_sec=cfg.duration_sec)

    out_mp4 = output_dir / f"tea_egg_{style}.mp4"
    encode_mp4(final_frames, wav_path, out_mp4, cfg)
    print(f"[{style}] Encoded MP4 -> {out_mp4} ({out_mp4.stat().st_size / 1024:.1f} KB) in {time.time() - t_start:.2f}s total.")

    qa_res: QAResult | None = None
    if not skip_thumbnails:
        qa_res = export_thumbnails_and_qa(final_frames, clean_frames, style, cfg, output_dir)
        print(
            f"[{style}] QA Self-Review: passed={qa_res.passed} | frames={qa_res.total_frames} | "
            f"pure_black_px={qa_res.pure_black_pixels} | pixel_exact={qa_res.pixel_grid_exact} | "
            f"subtitle_zone_ok={qa_res.subtitle_zone_ok}"
        )
        if not qa_res.passed:
            raise AssertionError(f"Automated QA check failed for style '{style}': {qa_res}")

    return out_mp4, final_frames, qa_res


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Tea Egg OpusCar Code Animation Renderer")
    parser.add_argument(
        "--style",
        choices=["crayon", "pixel", "both"],
        default=STYLE,
        help="Style to render ('crayon', 'pixel', or 'both'). Defaults to STYLE constant on Line 2.",
    )
    parser.add_argument("--force", action="store_true", help="Force full clean-plate re-render ignoring cache.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Skip re-exporting 192 JPG thumbnails on fast subtitle swap.")
    args = parser.parse_args()

    cfg = load_specs()
    styles = ["crayon", "pixel"] if args.style == "both" else [args.style]

    rendered_frames_by_style = {}
    for st in styles:
        _, fin_frames, _ = render_pipeline(
            style=st,
            subtitle_line=SUBTITLE_LINE,
            cfg=cfg,
            force=args.force,
            skip_thumbnails=args.fast_sub_only,
        )
        rendered_frames_by_style[st] = fin_frames

    if "crayon" in rendered_frames_by_style and "pixel" in rendered_frames_by_style and not args.fast_sub_only:
        comp_path = build_dual_style_comparison(
            rendered_frames_by_style["crayon"],
            rendered_frames_by_style["pixel"],
            cfg,
            REPO_ROOT / "output",
        )
        print(f"[both] Built dual-style frame-lock comparison -> {comp_path}")


if __name__ == "__main__":
    main()
