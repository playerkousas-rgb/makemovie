"""Post-process subtitle compositor (specs/08-typography).
Strictly overlays Chinese dialogue via code onto clean animation frames [5.5s - 8.0s].
Changing SUBTITLE_LINE in src/main.py only re-runs this lightweight overlay pass!
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from spec_loader import SpecConfig, ensure_font_path

_FONT_OBJ_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (font_name, size)
    if key not in _FONT_OBJ_CACHE:
        fpath = ensure_font_path(font_name)
        _FONT_OBJ_CACHE[key] = ImageFont.truetype(str(fpath), size)
    return _FONT_OBJ_CACHE[key]


def verify_glyphs(text: str, font_name: str, size: int = 44) -> None:
    """Assert that every visible character in `text` exists in the font (no tofu boxes!)."""
    font = _get_font(font_name, size)
    for ch in text:
        if ch.isspace():
            continue
        mask = font.getmask(ch)
        if mask.size[0] == 0 or mask.size[1] == 0:
            raise ValueError(f"Missing glyph for character '{ch}' (U+{ord(ch):04X}) in {font_name}!")


def apply_subtitle_overlay(
    clean_img: Image.Image,
    frame_idx: int,
    subtitle_text: str,
    style: str,
    cfg: SpecConfig,
) -> Image.Image:
    """Composite `subtitle_text` onto Shot 3 frames [132..191] without touching base art."""
    if not subtitle_text or not (cfg.subtitle_start_frame <= frame_idx <= cfg.subtitle_end_frame):
        return clean_img

    pal = cfg.palette_rgb(style)
    cx, cy = cfg.subtitle_pos  # (640, 636)
    local_f = frame_idx - cfg.subtitle_start_frame
    # Subtle 3-frame pop-in slide (8px -> 0px) at start of Shot 3
    pop_y = int(round((1.0 - min(1.0, local_f / 3.0)) * 8.0))

    if style == "crayon":
        font = _get_font(cfg.crayon_font_name, cfg.crayon_font_size)
        verify_glyphs(subtitle_text, cfg.crayon_font_name, cfg.crayon_font_size)

        out = clean_img.copy()
        draw = ImageDraw.Draw(out)
        bbox = draw.textbbox((0, 0), subtitle_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x, pad_y = 34, 15
        bx0 = cx - tw // 2 - pad_x
        by0 = cy - th // 2 - pad_y + pop_y
        bx1 = cx + tw // 2 + pad_x
        by1 = cy + th // 2 + pad_y + pop_y

        # Hand-drawn storybook caption card (warm cream paper #FAF1DC + roasted umber #3D2516 border)
        boil = (frame_idx // max(1, cfg.line_boil_hold_frames)) % 4
        pts = []
        steps = 28
        for i in range(steps):
            ang = 2.0 * math.pi * i / float(steps)
            # Superellipse rounded pill contour with subtle hand-drawn wobble
            ca, sa = math.cos(ang), math.sin(ang)
            rx = (bx1 - bx0) * 0.5
            ry = (by1 - by0) * 0.5
            sx_e = math.copysign(abs(ca) ** 0.55, ca) * rx
            sy_e = math.copysign(abs(sa) ** 0.72, sa) * ry
            wob_x = 1.4 * math.sin(i * 0.9 + boil * 1.7)
            wob_y = 1.2 * math.cos(i * 1.1 + boil * 1.3)
            pts.append((cx + sx_e + wob_x, (by0 + by1) * 0.5 + sy_e + wob_y))

        # Warm drop offset in amber glow + cream paper fill + umber outline
        shadow_pts = [(x + 4, y + 5) for x, y in pts]
        draw.polygon(shadow_pts, fill=pal["outline"])
        draw.polygon(pts, fill=pal["paper"])
        draw.line(pts + [pts[0]], fill=pal["outline"], width=5, joint="curve")

        # Cute warm amber accent dots on left & right of text
        for side_x in (bx0 + 16, bx1 - 16):
            my_d = (by0 + by1) // 2
            draw.ellipse((side_x - 5, my_d - 5, side_x + 5, my_d + 5), fill=pal["glow"])

        # Crisp Cantonese typography centered in the storybook card
        tx = cx - tw // 2 - bbox[0]
        ty = (by0 + by1) // 2 - th // 2 - bbox[1]
        draw.text((tx, ty), subtitle_text, font=font, fill=pal["outline"])
        return out

    elif style == "pixel":
        # Render RPG dialogue box & Cubic_11 at native 12px on the 320x180 pixel grid,
        # then upscale 4x NEAREST so 100.0% of pixels stay locked to exact 4x4 pixel blocks!
        u = cfg.pixel_upscale  # 4
        pw, ph = cfg.pixel_native_width, cfg.pixel_native_height
        native_size = 12
        font = _get_font(cfg.pixel_font_name, native_size)
        verify_glyphs(subtitle_text, cfg.pixel_font_name, native_size)

        # Extract exact 320x180 native grid from clean_img
        arr_full = np.asarray(clean_img, dtype=np.uint8)
        small = Image.fromarray(arr_full[0::u, 0::u].copy(), mode="RGB")
        draw = ImageDraw.Draw(small)
        draw.fontmode = "1"

        pcx = cx // u
        pcy = cy // u
        pop_p = pop_y // u

        bbox = draw.textbbox((0, 0), subtitle_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x, pad_y = 9, 4
        bx0 = pcx - tw // 2 - pad_x
        by0 = pcy - th // 2 - pad_y + pop_p
        bx1 = pcx + (tw - tw // 2) + pad_x
        by1 = pcy + (th - th // 2) + pad_y + pop_p

        # Classic 16-bit SNES RPG dialogue window on 320x180 grid:
        # 1px dark plum drop shadow + gold frame + deep night-indigo interior
        draw.rectangle((bx0 + 1, by0 + 1, bx1 + 1, by1 + 1), fill=pal["outline"])
        draw.rectangle((bx0, by0, bx1, by1), fill=pal["outline"])
        draw.rectangle((bx0 + 1, by0 + 1, bx1 - 1, by1 - 1), fill=pal["moon"])
        draw.rectangle((bx0 + 2, by0 + 2, bx1 - 2, by1 - 2), fill=pal["night"])

        # Blinking 16-bit RPG cursor at bottom-right of dialogue box
        if (frame_idx // 8) % 2 == 0:
            rx_c = bx1 - 5
            ry_c = by1 - 4
            draw.point([(rx_c, ry_c), (rx_c + 1, ry_c), (rx_c + 2, ry_c), (rx_c + 1, ry_c + 1)], fill=pal["glow"])

        tx = pcx - tw // 2 - bbox[0]
        ty = (by0 + by1) // 2 - th // 2 - bbox[1]

        # 1px dark plum shadow + bright crisp pixel text
        draw.text((tx + 1, ty + 1), subtitle_text, font=font, fill=pal["outline"])
        draw.text((tx, ty), subtitle_text, font=font, fill=pal["shirt"])

        return small.resize((cfg.width, cfg.height), resample=Image.Resampling.NEAREST)

    raise ValueError(f"Unknown style: {style}")
