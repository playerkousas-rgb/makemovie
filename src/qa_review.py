"""Frame-by-frame thumbnail exporter, contact sheet builder, and automated QA verifier."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from spec_loader import SpecConfig


@dataclass
class QAResult:
    style: str
    total_frames: int
    resolution_ok: bool
    pure_black_pixels: int
    pixel_grid_exact: bool
    subtitle_zone_ok: bool
    passed: bool


def export_thumbnails_and_qa(
    final_frames: Sequence[Image.Image],
    clean_frames: Sequence[Image.Image],
    style: str,
    cfg: SpecConfig,
    output_dir: Path,
) -> QAResult:
    """Save 192 individual frame thumbnails, contact sheets, and run programmatic QA checks."""
    thumbs_dir = output_dir / f"frames_{style}"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    n = len(final_frames)
    resolution_ok = n == cfg.total_frames and all(im.size == (cfg.width, cfg.height) for im in final_frames)

    pure_black_total = 0
    pixel_grid_exact = True
    subtitle_zone_ok = True

    thumb_w, thumb_h = 320, 180
    thumbs: List[Image.Image] = []

    for idx, (fin_im, cln_im) in enumerate(zip(final_frames, clean_frames)):
        arr = np.asarray(fin_im, dtype=np.uint8)
        # Check #1: Zero pure black #000000 anywhere
        black_cnt = int(np.sum((arr[:, :, 0] == 0) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 0)))
        pure_black_total += black_cnt

        # Check #2: In pixel mode, every 4x4 block must be 100% uniform (zero bilinear blur!)
        if style == "pixel" and pixel_grid_exact:
            top_left = arr[0::4, 0::4]
            reconstructed = np.repeat(np.repeat(top_left, 4, axis=0), 4, axis=1)
            if not np.array_equal(arr, reconstructed):
                pixel_grid_exact = False

        # Check #3: Subtitle overlay strictly restricted to Shot 3 [132..191] bottom safe zone
        cln_arr = np.asarray(cln_im, dtype=np.uint8)
        if idx < cfg.subtitle_start_frame:
            if not np.array_equal(arr, cln_arr):
                subtitle_zone_ok = False
        else:
            diff_ys = np.where(np.any(arr != cln_arr, axis=-1))[0]
            if len(diff_ys) == 0 or int(diff_ys.min()) < int(cfg.height * 0.78):
                subtitle_zone_ok = False

        # Save per-frame thumbnail (NEAREST for pixel, LANCZOS for crayon)
        resamp = Image.Resampling.NEAREST if style == "pixel" else Image.Resampling.LANCZOS
        th = fin_im.resize((thumb_w, thumb_h), resample=resamp)
        th.save(thumbs_dir / f"frame_{idx:03d}.jpg", quality=90)
        thumbs.append(th)

    # 1) Build high-readability 48-frame Contact Sheet (every 4 frames: 6 cols x 8 rows)
    cols_48, rows_48 = 6, 8
    pad = 8
    label_h = 22
    cs_w = cols_48 * (thumb_w + pad) + pad
    cs_h = rows_48 * (thumb_h + label_h + pad) + pad
    cs_img = Image.new("RGB", (cs_w, cs_h), (38, 30, 26))
    cs_draw = ImageDraw.Draw(cs_img)
    font = ImageFont.load_default()

    sample_indices = [min(n - 1, i * 4) for i in range(47)] + [n - 1]
    for slot, f_idx in enumerate(sample_indices):
        r = slot // cols_48
        c = slot % cols_48
        x = pad + c * (thumb_w + pad)
        y = pad + r * (thumb_h + label_h + pad)
        cs_img.paste(thumbs[f_idx], (x, y))
        shot_no = 1 if f_idx <= 59 else (2 if f_idx <= 131 else 3)
        t_s = f_idx / float(cfg.fps)
        cs_draw.text(
            (x + 4, y + thumb_h + 4),
            f"F{f_idx:03d} | {t_s:4.2f}s | Shot {shot_no}",
            fill=(245, 235, 215),
            font=font,
        )
    cs_img.save(output_dir / f"contact_sheet_{style}.jpg", quality=92)

    # 2) Build complete 192-frame Every-Single-Frame Grid (12 cols x 16 rows)
    mini_w, mini_h = 192, 108
    cols_all, rows_all = 12, 16
    all_w = cols_all * (mini_w + 4) + 4
    all_h = rows_all * (mini_h + 16) + 4
    all_img = Image.new("RGB", (all_w, all_h), (34, 26, 24))
    all_draw = ImageDraw.Draw(all_img)
    resamp_mini = Image.Resampling.NEAREST if style == "pixel" else Image.Resampling.BILINEAR
    for f_idx in range(n):
        r = f_idx // cols_all
        c = f_idx % cols_all
        x = 4 + c * (mini_w + 4)
        y = 4 + r * (mini_h + 16)
        mini = final_frames[f_idx].resize((mini_w, mini_h), resample=resamp_mini)
        all_img.paste(mini, (x, y))
        all_draw.text((x + 2, y + mini_h + 2), f"#{f_idx:03d} ({f_idx/cfg.fps:.2f}s)", fill=(235, 224, 205), font=font)
    all_img.save(output_dir / f"all_192_frames_{style}.jpg", quality=88)

    passed = resolution_ok and (pure_black_total == 0) and pixel_grid_exact and subtitle_zone_ok
    return QAResult(
        style=style,
        total_frames=n,
        resolution_ok=resolution_ok,
        pure_black_pixels=pure_black_total,
        pixel_grid_exact=pixel_grid_exact,
        subtitle_zone_ok=subtitle_zone_ok,
        passed=passed,
    )


def build_dual_style_comparison(
    crayon_frames: Sequence[Image.Image],
    pixel_frames: Sequence[Image.Image],
    cfg: SpecConfig,
    output_dir: Path,
) -> Path:
    """Create side-by-side comparison strip proving identical camera, timing & rig across A & B."""
    beats = [
        (12, "Shot 1 (0.50s) Empty Store"),
        (52, "Shot 1 (2.17s) Dolly-In Last Egg"),
        (76, "Shot 2 (3.17s) Clerk Walks In"),
        (104, "Shot 2 (4.33s) Reach & Hesitate"),
        (124, "Shot 2 (5.17s) Warm Smile"),
        (155, "Shot 3 (6.46s) Hold Egg + Subtitle"),
    ]
    tw, th = 480, 270
    pad = 12
    header_h = 26
    w = 2 * tw + 3 * pad
    h = len(beats) * (th + header_h + pad) + pad
    comp = Image.new("RGB", (w, h), (36, 28, 24))
    draw = ImageDraw.Draw(comp)
    font = ImageFont.load_default()

    for row, (f_idx, label) in enumerate(beats):
        y = pad + row * (th + header_h + pad)
        c_im = crayon_frames[f_idx].resize((tw, th), resample=Image.Resampling.LANCZOS)
        p_im = pixel_frames[f_idx].resize((tw, th), resample=Image.Resampling.NEAREST)
        comp.paste(c_im, (pad, y + header_h))
        comp.paste(p_im, (2 * pad + tw, y + header_h))
        draw.text((pad + 4, y + 6), f"[Version A: Crayon] F{f_idx:03d} - {label}", fill=(250, 241, 220), font=font)
        draw.text((2 * pad + tw + 4, y + 6), f"[Version B: 16-bit Pixel] F{f_idx:03d} - {label}", fill=(255, 230, 109), font=font)

    out_path = output_dir / "dual_style_comparison.jpg"
    comp.save(out_path, quality=92)
    return out_path
