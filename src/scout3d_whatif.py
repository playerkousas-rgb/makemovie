SUBTITLE_LINES = {
    1: "冇 SCOUT 3D：查書辛苦、\n阿媽聯錯晒、仲俾領袖鬧！",
    2: "如果你有 SCOUT 3D ——\n揀個章自動上身，方塊定波波都啱晒位！",
    3: "完全唔使查書，\n媽媽望住 3D 人仔照聯一定啱！",
    4: "揀章即見位・唔怕俾人鬧\n—— SCOUT 3D！",
}
SERIES_BADGE = "如果系列 EP.01 · 如果你有 SCOUT 3D"

"""What If 3D Short Pipeline — EP.01: '如果你有 SCOUT 3D'
- Format: 9:16 Vertical HD (720 x 1280), 24 FPS, 11.50s (276 frames)
- Visual Style: 波波圓滑 3D 風 (with Treatment 3 Blocky-to-Bobo badge-lock showcase!)
- Edit `SUBTITLE_LINES` at top of file to update subtitles in ~1.5s via clean-plate cache!
"""

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from camera import clamp, lerp, smoothstep
from engine3d import Camera3D, Scene3D, hex_rgb01, rot_y, v3
from scout3d_characters import (
    COL,
    draw_handbook_stack,
    draw_leader_figure,
    draw_mom_figure,
    draw_scout_figure,
    draw_turntable_pedestal,
)
from spec_loader import ensure_font_path

WIDTH = 720
HEIGHT = 1280
FPS = 24
TOTAL_FRAMES = 276  # 11.50 seconds @ 24fps

# Shot frame boundaries:
# Shot 1: 000..071 (0.00s - 3.00s) -> Disaster without SCOUT 3D
# Shot 2: 072..155 (3.00s - 6.50s) -> SCOUT 3D auto-badge placement + Blocky -> Bobo 3D lock!
# Shot 3: 156..215 (6.50s - 9.00s) -> Mom effortlessly follows 3D turntable, zero book-hunting!
# Shot 4: 216..275 (9.00s - 11.50s) -> Bobo + Blocky Scouts salute together, Leader praises!


def _shot_of_frame(f: int) -> int:
    if f <= 71:
        return 1
    if f <= 155:
        return 2
    if f <= 215:
        return 3
    return 4


def render_clean_3d_frame(frame_idx: int) -> Image.Image:
    """Render one pure 3D frame (zero baked text) at 720x1280."""
    t = frame_idx / float(FPS)
    shot = _shot_of_frame(frame_idx)

    if shot == 1:
        # --- SHOT 1 [0.00 - 3.00s]: Disaster Without SCOUT 3D ---
        u = frame_idx / 71.0
        e = smoothstep(u)
        shake_x = math.sin(t * 26.0) * 0.032 * smoothstep((t - 1.2) / 0.5) * (1.0 - smoothstep((t - 2.4) / 0.5))
        cam = Camera3D(
            pos=v3(lerp(0.0, 0.04, e) + shake_x, lerp(2.08, 1.96, e), lerp(8.45, 7.65, e)),
            target=v3(0.0, lerp(1.38, 1.44, e), 0.0),
            fov_deg=38.0,
            roll_deg=math.sin(t * 9.0) * 1.0 * (1.0 - 0.5 * u),
        )
        sc = Scene3D(
            WIDTH,
            HEIGHT,
            cam,
            bg_top=hex_rgb01("#3B3348"),
            bg_bot=hex_rgb01("#63566E"),
            floor_y=0.0,
            floor_color=hex_rgb01("#574D63"),
            key_dir=(-0.45, 0.78, 0.55),
            rim_color=hex_rgb01("#FF9E9E"),
        )
        # Left: Dizzy Mom + intimidating stack of thick uniform manuals clearly visible in front!
        draw_mom_figure(sc, v3(-0.88, 0.0, -0.35), yaw_deg=22.0, scale=0.86, mood="dizzy", t_sec=t)
        draw_handbook_stack(sc, v3(-0.82, 0.0, 0.62), yaw_deg=18.0, scale=0.90)

        # Center foreground: Nervous Bobo 3D Scout Kid with badges sewed in WRONG places!
        wobble_yaw = math.sin(t * 7.5) * 6.0
        draw_scout_figure(
            sc,
            v3(-0.02, 0.0, 0.28),
            yaw_deg=wobble_yaw,
            scale=0.90,
            style_mode="bobo",
            expression="nervous",
            salute=0.0,
            badge_mode="wrong",
            show_sash=0.0,
        )

        # Right: Stern Scout Leader raising 3D Red X warning sign!
        draw_leader_figure(sc, v3(0.86, 0.0, -0.15), yaw_deg=-24.0, scale=0.92, mood="scold", t_sec=t)
        return sc.render()

    elif shot == 2:
        # --- SHOT 2 [3.00 - 6.50s]: SCOUT 3D Studio! Tick badge -> Auto-appears on 3D Figure! ---
        u = (frame_idx - 72) / 83.0
        lt = t - 3.00  # 0.0 .. 3.50s

        # Target slightly higher (y=1.82) so 3D figurine sits cleanly below the top SCOUT 3D UI panel!
        cam = Camera3D(
            pos=v3(lerp(0.10, -0.08, smoothstep(u)), lerp(2.15, 2.02, smoothstep(u)), lerp(6.95, 6.35, smoothstep(u))),
            target=v3(0.0, 1.80, 0.0),
            fov_deg=36.0,
        )
        sc = Scene3D(
            WIDTH,
            HEIGHT,
            cam,
            bg_top=hex_rgb01("#8AC6F2"),
            bg_bot=hex_rgb01("#DCF0FC"),
            floor_y=0.0,
            floor_color=hex_rgb01("#CBE6F8"),
            key_dir=(-0.50, 0.72, 0.65),
            rim_color=hex_rgb01("#FFFFFF"),
        )

        draw_turntable_pedestal(sc, (0.0, 0.0), y_top=0.14, radius=1.02)

        if lt < 1.35:
            yaw = lerp(-8.0, 42.0, smoothstep(lt / 1.15))
        elif lt < 2.35:
            yaw = lerp(42.0, -34.0, smoothstep((lt - 1.35) / 0.95))
        else:
            yaw = lerp(-34.0, 14.0, smoothstep((lt - 2.35) / 1.05))

        prog_map = {
            "membership": clamp((lt - 0.18) / 0.32),
            "link_award": clamp((lt - 0.26) / 0.32),
            "troop_tape": clamp((lt - 0.55) / 0.32),
            "district": clamp((lt - 0.68) / 0.32),
            "patrol": clamp((lt - 0.95) / 0.32),
            "prof_sleeve_1": clamp((lt - 1.32) / 0.32),
            "prof_sleeve_2": clamp((lt - 1.42) / 0.32),
        }
        sash_vis = smoothstep((lt - 1.35) / 0.35)

        morph_t = 1.85
        mode = "blocky" if lt < morph_t else "bobo"

        draw_scout_figure(
            sc,
            v3(0.0, 0.14, 0.0),
            yaw_deg=yaw,
            scale=0.96,
            style_mode=mode,
            expression="happy",
            salute=0.0,
            badge_mode="animated",
            badge_progress=prog_map,
            show_sash=sash_vis,
        )

        # Golden 3D holographic transformation ring sweeping down at lt in [1.68, 2.08]!
        if 1.68 <= lt <= 2.08:
            ring_u = (lt - 1.68) / 0.40
            ring_y = lerp(2.75, 0.20, ring_u)
            for k in range(16):
                ang = 2.0 * math.pi * k / 16.0 + lt * 8.0
                sc.add_sphere(
                    v3(0.72 * math.cos(ang), ring_y, 0.72 * math.sin(ang)),
                    0.052,
                    COL["gold"],
                    roughness=0.1,
                    emissive=(0.55, 0.42, 0.08),
                )

        return sc.render()

    elif shot == 3:
        # --- SHOT 3 [6.50 - 9.00s]: Mom Effortlessly Copies Rotating 3D Figure (No Book Hunting!) ---
        u = (frame_idx - 156) / 59.0
        lt = t - 6.50

        cam = Camera3D(
            pos=v3(lerp(-0.06, 0.04, smoothstep(u)), 1.96, lerp(7.65, 7.05, smoothstep(u))),
            target=v3(0.0, 1.40, 0.0),
            fov_deg=37.0,
        )
        sc = Scene3D(
            WIDTH,
            HEIGHT,
            cam,
            bg_top=hex_rgb01("#FCE6C9"),
            bg_bot=hex_rgb01("#FFF7EA"),
            floor_y=0.0,
            floor_color=hex_rgb01("#F2DEC0"),
            key_dir=(-0.48, 0.75, 0.60),
            rim_color=hex_rgb01("#FFF6D6"),
        )

        # Left-back: The thick handbook stack pushed aside & ignored!
        draw_handbook_stack(sc, v3(-0.98, 0.0, -0.75), yaw_deg=-26.0, scale=0.78)

        # Left-Center: Happy Bobo 3D Mom smiling brightly!
        draw_mom_figure(sc, v3(-0.56, 0.0, 0.14), yaw_deg=22.0, scale=0.92, mood="happy", t_sec=t)

        # Right-Center: Elevated 3D Display Stand with rotating Mini SCOUT 3D Figure!
        sc.add_cylinder(v3(0.58, 0.0, 0.14), v3(0.58, 0.82, 0.14), 0.15, COL["pedestal_rim"], roughness=0.35)
        draw_turntable_pedestal(sc, (0.58, 0.14), y_top=0.92, radius=0.62)
        holo_yaw = -25.0 + lt * 52.0
        draw_scout_figure(
            sc,
            v3(0.58, 0.92, 0.14),
            yaw_deg=holo_yaw,
            scale=0.56,
            style_mode="bobo",
            expression="happy",
            salute=0.0,
            badge_mode="correct",
            show_sash=1.0,
        )

        for sp_i in range(4):
            ang = lt * 3.2 + sp_i * (math.pi * 0.5)
            sc.add_sphere(
                v3(0.58 + 0.56 * math.cos(ang), 1.66 + 0.16 * math.sin(ang * 2.0), 0.14 + 0.56 * math.sin(ang)),
                0.040,
                COL["gold"],
                roughness=0.1,
                emissive=(0.45, 0.36, 0.05),
            )

        return sc.render()

    else:
        # --- SHOT 4 [9.00 - 11.50s]: Grand Finale — Bobo + Blocky Scouts Salute, Leader Praises! ---
        u = (frame_idx - 216) / 59.0
        lt = t - 9.00
        salute_u = smoothstep(lt / 0.45)

        cam = Camera3D(
            pos=v3(0.0, lerp(2.06, 1.96, smoothstep(u)), lerp(8.75, 7.95, smoothstep(u))),
            target=v3(0.0, lerp(1.42, 1.48, smoothstep(u)), 0.0),
            fov_deg=38.5,
        )
        sc = Scene3D(
            WIDTH,
            HEIGHT,
            cam,
            bg_top=hex_rgb01("#7EC4CF"),
            bg_bot=hex_rgb01("#E8F8F5"),
            floor_y=0.0,
            floor_color=hex_rgb01("#CDEAE5"),
            key_dir=(-0.45, 0.76, 0.62),
            rim_color=hex_rgb01("#FFF8DC"),
        )

        # Left buddy: Blocky 3D Scout with 100% matching badge placement & 3-finger salute (clear face!)
        draw_scout_figure(
            sc,
            v3(-0.98, 0.0, -0.18),
            yaw_deg=15.0,
            scale=0.82,
            style_mode="blocky",
            expression="happy",
            salute=salute_u,
            badge_mode="correct",
            show_sash=1.0,
        )

        # Center-Front Hero: Bobo Smooth 3D Scout on SCOUT 3D pedestal giving crisp 3-finger salute!
        draw_turntable_pedestal(sc, (-0.02, 0.28), y_top=0.13, radius=0.70)
        draw_scout_figure(
            sc,
            v3(-0.02, 0.13, 0.28),
            yaw_deg=8.0,
            scale=0.88,
            style_mode="bobo",
            expression="happy",
            salute=salute_u,
            badge_mode="correct",
            show_sash=1.0,
        )

        # Right: Beaming Bobo 3D Scout Leader giving big unobstructed Thumbs-Up + Glowing Green Check!
        draw_leader_figure(sc, v3(0.90, 0.0, -0.06), yaw_deg=-20.0, scale=0.88, mood="praise", t_sec=t)
        return sc.render()


# ---------------------------------------------------------------------------
# Post-Process Typography & SCOUT 3D UI Overlay (100% Crisp Code Typography!)
# ---------------------------------------------------------------------------
_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    fname = "LXGWWenKaiTC-Medium.ttf" if bold else "Iansui-Regular.ttf"
    key = (fname, size)
    if key not in _FONT_CACHE:
        fp = ensure_font_path(fname)
        _FONT_CACHE[key] = ImageFont.truetype(str(fp), size)
    return _FONT_CACHE[key]


def _verify_text_glyphs(text: str) -> None:
    f = _font(32)
    for ch in text:
        if ch.isspace():
            continue
        m = f.getmask(ch)
        if m.size[0] == 0 or m.size[1] == 0:
            raise ValueError(f"Missing glyph '{ch}' in font!")


def _tokenize_cjk_ascii(line: str) -> List[str]:
    """Keep 'SCOUT 3D' and ASCII words intact so they never split mid-token across lines."""
    tokens: List[str] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i:].startswith("SCOUT 3D"):
            tokens.append("SCOUT 3D")
            i += len("SCOUT 3D")
        elif line[i].isascii() and (line[i].isalnum() or line[i] in "._-"):
            j = i + 1
            while j < n and line[j].isascii() and (line[j].isalnum() or line[j] in "._-"):
                j += 1
            tokens.append(line[i:j])
            i = j
        else:
            tokens.append(line[i])
            i += 1
    return tokens


def _wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    lines: List[str] = []
    for raw_line in text.split("\n"):
        cur = ""
        for tok in _tokenize_cjk_ascii(raw_line):
            cand = cur + tok
            bb = draw.textbbox((0, 0), cand, font=font)
            if (bb[2] - bb[0]) <= max_w or not cur:
                cur = cand
            else:
                lines.append(cur.rstrip())
                cur = tok.lstrip()
        if cur:
            lines.append(cur)
    return lines


def overlay_scout3d_ui_and_subtitles(
    clean_img: Image.Image,
    frame_idx: int,
    subtitle_map: Dict[int, str],
    series_badge: str,
) -> Image.Image:
    """Post-process 2D vector UI & Shorts subtitle overlay (never touches 3D base render!)."""
    out = clean_img.convert("RGBA")
    ui_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui_layer)

    t = frame_idx / float(FPS)
    shot = _shot_of_frame(frame_idx)

    # 1. Top Reels Series Header Pill (y = 58..112, safe below status bar)
    _verify_text_glyphs(series_badge)
    f_tag = _font(25, bold=True)
    tb = draw.textbbox((0, 0), series_badge, font=f_tag)
    tw_tag = tb[2] - tb[0]
    th_tag = tb[3] - tb[1]
    px0 = WIDTH // 2 - tw_tag // 2 - 24
    px1 = WIDTH // 2 + tw_tag // 2 + 24
    py0, py1 = 56, 56 + th_tag + 22
    draw.rounded_rectangle((px0, py0 + 3, px1, py1 + 3), radius=24, fill=(18, 28, 45, 110))
    pill_bg = (198, 48, 56, 232) if shot == 1 else (31, 48, 82, 232)
    draw.rounded_rectangle((px0, py0, px1, py1), radius=24, fill=pill_bg, outline=(255, 255, 255, 210), width=2)
    draw.text((WIDTH // 2 - tw_tag // 2 - tb[0], (py0 + py1) // 2 - th_tag // 2 - tb[1]), series_badge, font=f_tag, fill=(255, 255, 255, 255))

    # 2. Shot 2 Interactive SCOUT 3D Top Banner Card (sits cleanly ABOVE the 3D figurine — zero face overlap!)
    if shot == 2:
        lt = t - 3.00
        card_x0, card_y0 = 36, 122
        card_x1, card_y1 = WIDTH - 36, 286
        draw.rounded_rectangle((card_x0, card_y0 + 5, card_x1, card_y1 + 5), radius=20, fill=(20, 35, 60, 60))
        draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=20, fill=(255, 255, 255, 238), outline=(206, 224, 242, 255), width=2)

        f_hdr = _font(20, bold=True)
        f_row = _font(19, bold=False)
        hdr_txt = "SCOUT3D · 撳章自動上身"
        _verify_text_glyphs(hdr_txt)
        draw.text((card_x0 + 20, card_y0 + 13), hdr_txt, font=f_hdr, fill=(31, 48, 82, 255))

        # Mode switch pill on top-right of card (with crisp vector checkmark when locked in Bobo Smooth!)
        is_bobo_now = lt >= 1.85
        mode_txt = "外觀：波波流線" if is_bobo_now else "外觀：簡約方塊"
        _verify_text_glyphs(mode_txt)
        mb = draw.textbbox((0, 0), mode_txt, font=f_row)
        mw = mb[2] - mb[0]
        extra_chk = 24 if is_bobo_now else 0
        mx1 = card_x1 - 16
        mx0 = mx1 - mw - 28 - extra_chk
        my0, my1 = card_y0 + 9, card_y0 + 44
        m_fill = (38, 166, 98, 245) if is_bobo_now else (62, 80, 112, 235)
        draw.rounded_rectangle((mx0, my0, mx1, my1), radius=15, fill=m_fill)
        draw.text((mx0 + 14 - mb[0], my0 + 6 - mb[1]), mode_txt, font=f_row, fill=(255, 255, 255, 255))
        if is_bobo_now:
            cx_k, cy_k = mx1 - 20, (my0 + my1) // 2 + 1
            draw.line([(cx_k - 6, cy_k), (cx_k - 1, cy_k + 5), (cx_k + 7, cy_k - 5)], fill=(255, 255, 255, 255), width=3)

        draw.line([(card_x0 + 16, card_y0 + 52), (card_x1 - 16, card_y0 + 52)], fill=(228, 236, 245, 255), width=2)

        # Clean 2x2 grid of authentic SCOUT3D orange badge-toggle switches!
        toggles = [
            (0.18, "世界會員章"),
            (0.55, "旅條 · 區章"),
            (0.95, "小隊章"),
            (1.35, "專科章 ×12"),
        ]
        col_w = (card_x1 - card_x0 - 36) // 2
        for idx_t, (trig_t, label) in enumerate(toggles):
            _verify_text_glyphs(label)
            r_grid = idx_t // 2
            c_grid = idx_t % 2
            gx = card_x0 + 20 + c_grid * (col_w + 12)
            gy = card_y0 + 64 + r_grid * 52
            is_on = lt >= trig_t
            draw.text((gx, gy + 5), label, font=f_row, fill=(32, 44, 64, 255) if is_on else (135, 145, 160, 255))
            tx1 = gx + col_w - 14
            tx0 = tx1 - 48
            ty0, ty1 = gy + 4, gy + 30
            t_col = (242, 121, 28, 255) if is_on else (204, 212, 222, 255)
            draw.rounded_rectangle((tx0, ty0, tx1, ty1), radius=13, fill=t_col)
            kx = tx1 - 13 if is_on else tx0 + 13
            ky = (ty0 + ty1) // 2
            draw.ellipse((kx - 10, ky - 10, kx + 10, ky + 10), fill=(255, 255, 255, 255))

    # 3. Bottom Reels/Shorts Subtitle Card (y centered around 1075, well inside 720x1280 safe zone!)
    sub_text = subtitle_map.get(shot, "").strip()
    if sub_text:
        _verify_text_glyphs(sub_text)
        f_sub = _font(33, bold=True)
        wrapped = _wrap_text_to_width(draw, sub_text, f_sub, max_w=WIDTH - 104)

        # Pop-in animation on first 4 frames of each shot
        shot_starts = {1: 0, 2: 72, 3: 156, 4: 216}
        local_f = frame_idx - shot_starts[shot]
        pop_offset = int(round((1.0 - min(1.0, local_f / 4.0)) * 12.0))

        line_bboxes = [draw.textbbox((0, 0), ln, font=f_sub) for ln in wrapped]
        line_ws = [bb[2] - bb[0] for bb in line_bboxes]
        line_hs = [bb[3] - bb[1] for bb in line_bboxes]
        line_gap = 12
        block_w = max(line_ws)
        block_h = sum(line_hs) + line_gap * (len(wrapped) - 1)

        cy_sub = 1076 + pop_offset
        pad_x, pad_y = 30, 20
        bx0 = WIDTH // 2 - block_w // 2 - pad_x
        bx1 = WIDTH // 2 + block_w // 2 + pad_x
        by0 = cy_sub - block_h // 2 - pad_y
        by1 = cy_sub + block_h // 2 + pad_y

        # Crisp modern Reels caption box with subtle shadow & accent border
        accent_border = (255, 112, 112, 245) if shot == 1 else (247, 201, 66, 250)
        draw.rounded_rectangle((bx0, by0 + 6, bx1, by1 + 6), radius=22, fill=(12, 18, 30, 120))
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=22, fill=(22, 31, 48, 236), outline=accent_border, width=3)

        cur_y = cy_sub - block_h // 2
        for ln, bb, lw, lh in zip(wrapped, line_bboxes, line_ws, line_hs):
            tx = WIDTH // 2 - lw // 2 - bb[0]
            ty = cur_y - bb[1]
            # Subtle dark stroke + bright warm white/gold text
            draw.text((tx + 2, ty + 2), ln, font=f_sub, fill=(12, 16, 26, 240))
            txt_col = (255, 246, 210, 255) if "SCOUT 3D" in ln else (255, 255, 255, 255)
            draw.text((tx, ty), ln, font=f_sub, fill=txt_col)
            cur_y += lh + line_gap

    return Image.alpha_composite(out, ui_layer).convert("RGB")


# ---------------------------------------------------------------------------
# Synced Procedural Audio Track (11.50s Stereo 44.1kHz)
# ---------------------------------------------------------------------------
def synthesize_scout3d_audio(out_wav: Path, duration_sec: float = 11.5) -> Path:
    sr = 44100
    n = int(round(duration_sec * sr))
    t = np.arange(n, dtype=np.float32) / float(sr)
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    def m2f(m: float) -> float:
        return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

    def note(st: float, dur: float, freq: float, amp: float, pan: float = 0.0, kind: str = "pluck") -> None:
        i0 = max(0, int(st * sr))
        i1 = min(n, int((st + dur) * sr))
        if i1 <= i0:
            return
        lt = np.arange(i1 - i0, dtype=np.float32) / float(sr)
        if kind == "pluck":
            env = np.minimum(1.0, lt / 0.008) * np.exp(-lt * 4.2)
            sig = (0.70 * np.sin(2 * math.pi * freq * lt) + 0.25 * np.sin(4 * math.pi * freq * lt) + 0.05 * np.sin(6 * math.pi * freq * lt)) * env
        elif kind == "warm":
            env = np.minimum(1.0, lt / 0.02) * np.exp(-lt * 1.8) * np.minimum(1.0, (dur - lt) / 0.04)
            sig = (0.75 * np.sin(2 * math.pi * freq * lt) + 0.25 * np.sin(4 * math.pi * freq * lt)) * env
        elif kind == "buzz":
            env = np.minimum(1.0, lt / 0.01) * np.exp(-lt * 3.5)
            sig = np.tanh(2.5 * np.sin(2 * math.pi * freq * lt) + 1.2 * np.sin(2 * math.pi * (freq * 1.06) * lt)) * env * 0.5
        else:
            env = np.minimum(1.0, lt / 0.004) * np.exp(-lt * 12.0)
            sig = np.sin(2 * math.pi * freq * lt) * env
        left[i0:i1] += sig * amp * math.sqrt(0.5 * (1.0 - pan))
        right[i0:i1] += sig * amp * math.sqrt(0.5 * (1.0 + pan))

    # Shot 1 [0 - 3.0s]: Quirky comedic minor tiptoe + Red-X buzzer at 1.65s!
    s1_notes = [(0.10, 62), (0.48, 65), (0.86, 68), (1.24, 67), (1.95, 65), (2.38, 62)]
    for st, md in s1_notes:
        note(st, 0.36, m2f(md), 0.22, pan=-0.1, kind="pluck")
    note(1.58, 0.38, m2f(49), 0.26, pan=0.25, kind="buzz")  # Leader Red X cue!

    # Shot 2 [3.0 - 6.5s]: Bright C-major SCOUT 3D reveal + 4 UI badge-pop chimes + Morph sparkle!
    for idx_ch, semi in enumerate((60, 64, 67, 72)):
        note(3.00 + idx_ch * 0.04, 0.55, m2f(semi), 0.20, pan=0.0, kind="warm")

    # 4 Badge Toggle POP-SNAP cues (synced to 3.18s, 3.55s, 3.95s, 4.35s!)
    for idx_b, trig in enumerate((3.18, 3.55, 3.95, 4.35)):
        note(trig, 0.16, m2f(76 + idx_b * 2), 0.26, pan=0.2, kind="pluck")
        note(trig + 0.07, 0.18, m2f(84 + idx_b * 2), 0.22, pan=0.15, kind="pop")

    # Golden Blocky -> Bobo Smooth morph arpeggio at 4.75s!
    for k, md in enumerate((67, 71, 74, 79, 83, 86)):
        note(4.72 + k * 0.05, 0.35, m2f(md), 0.18, pan=(k - 2.5) * 0.12, kind="pluck")

    # Upbeat background groove across Shots 2, 3, 4 [3.0 - 11.5s]
    groove = [
        (3.2, 60), (3.7, 64), (4.2, 67), (4.7, 69), (5.2, 67), (5.7, 64), (6.1, 67),
        (6.55, 65), (7.05, 69), (7.55, 72), (8.05, 74), (8.50, 72),
        (9.02, 67), (9.45, 72), (9.90, 76), (10.35, 79),
    ]
    for st, md in groove:
        note(st, 0.44, m2f(md), 0.18, pan=-0.12, kind="pluck")
        note(st, 0.42, m2f(md - 12), 0.15, pan=0.10, kind="warm")

    # Shot 4 [9.02s] Salute & Leader Praise triumphant chord!
    for semi in (60, 64, 67, 72, 76):
        note(10.55, 0.88, m2f(semi), 0.20, pan=0.0, kind="warm")

    fade = np.clip(t / 0.06, 0.0, 1.0) * np.clip((duration_sec - t) / 0.18, 0.0, 1.0)
    left *= fade
    right *= fade
    peak = max(1e-5, float(max(np.max(np.abs(left)), np.max(np.abs(right)))))
    scale = min(1.8, 0.72 / peak)
    stereo = np.stack([left * scale, right * scale], axis=1)
    pcm16 = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return out_wav


# ---------------------------------------------------------------------------
# Clean-Plate Cache, Multiprocessing 3D Render, Thumbnails & MP4 Mux
# ---------------------------------------------------------------------------
def _compute_3d_scene_hash() -> str:
    h = hashlib.sha256()
    for fname in ("engine3d.py", "scout3d_characters.py"):
        h.update(fname.encode("utf-8"))
        h.update((SRC_DIR / fname).read_bytes())
    # Hash render_clean_3d_frame source code only (excluding SUBTITLE_LINES at top!)
    src_lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    body_start = next(i for i, ln in enumerate(src_lines) if ln.startswith("def _shot_of_frame"))
    body_end = next(i for i, ln in enumerate(src_lines) if ln.startswith("# Post-Process Typography"))
    h.update("\n".join(src_lines[body_start:body_end]).encode("utf-8"))
    return h.hexdigest()[:16]


def _worker_render_task(args: Tuple[int, str]) -> int:
    f_idx, out_png = args
    im = render_clean_3d_frame(f_idx)
    im.save(out_png, format="PNG", compress_level=1)
    return f_idx


def get_or_render_3d_plates(force: bool = False) -> Tuple[List[Image.Image], bool]:
    plate_dir = REPO_ROOT / ".cache" / "scout3d_clean_plates"
    plate_dir.mkdir(parents=True, exist_ok=True)
    manifest = plate_dir / "manifest.json"
    expected_hash = _compute_3d_scene_hash()

    cache_hit = False
    if not force and manifest.exists():
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            if (
                meta.get("hash") == expected_hash
                and meta.get("total_frames") == TOTAL_FRAMES
                and all((plate_dir / f"plate_{i:03d}.png").exists() for i in range(TOTAL_FRAMES))
            ):
                cache_hit = True
        except Exception:
            cache_hit = False

    if cache_hit:
        print(f"[scout3d] CACHE HIT (hash={expected_hash}): Reusing {TOTAL_FRAMES} clean 3D frames (0 3D re-renders)!")
    else:
        t0 = time.time()
        workers = min(max(1, (os.cpu_count() or 2)), 8)
        print(f"[scout3d] Rendering {TOTAL_FRAMES} true-3D frames @ {WIDTH}x{HEIGHT} ({FPS}fps) on {workers} workers...")
        tasks = [(i, str(plate_dir / f"plate_{i:03d}.png")) for i in range(TOTAL_FRAMES)]
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for done_i, _ in enumerate(pool.imap_unordered(_worker_render_task, tasks, chunksize=6), 1):
                if done_i % 46 == 0 or done_i == TOTAL_FRAMES:
                    print(f"  [scout3d] {done_i}/{TOTAL_FRAMES} 3D frames rendered...")
        manifest.write_text(json.dumps({"hash": expected_hash, "total_frames": TOTAL_FRAMES}, indent=2), encoding="utf-8")
        print(f"[scout3d] 3D base render finished in {time.time() - t0:.2f}s.")

    frames: List[Image.Image] = []
    for i in range(TOTAL_FRAMES):
        with Image.open(plate_dir / f"plate_{i:03d}.png") as im:
            frames.append(im.convert("RGB"))
    return frames, cache_hit


def export_scout3d_contact_sheet(frames: Sequence[Image.Image], output_dir: Path) -> Path:
    thumbs_dir = output_dir / "frames_scout3d"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    tw, th = 180, 320
    thumbs: List[Image.Image] = []
    for i, im in enumerate(frames):
        t_im = im.resize((tw, th), resample=Image.Resampling.LANCZOS)
        t_im.save(thumbs_dir / f"frame_{i:03d}.jpg", quality=88)
        thumbs.append(t_im)

    # 8 cols x 6 rows = 48 sampled frames across all 11.5s
    cols, rows = 8, 6
    pad = 8
    lh = 22
    cw = cols * (tw + pad) + pad
    ch = rows * (th + lh + pad) + pad
    sheet = Image.new("RGB", (cw, ch), (24, 30, 42))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    indices = [min(len(frames) - 1, round(i * (len(frames) - 1) / 47.0)) for i in range(48)]
    for slot, f_idx in enumerate(indices):
        r = slot // cols
        c = slot % cols
        x = pad + c * (tw + pad)
        y = pad + r * (th + lh + pad)
        sheet.paste(thumbs[f_idx], (x, y))
        sh = _shot_of_frame(f_idx)
        draw.text((x + 4, y + th + 4), f"F{f_idx:03d} {f_idx/FPS:4.1f}s S{sh}", fill=(235, 242, 250), font=font)

    out_p = output_dir / "contact_sheet_scout3d.jpg"
    sheet.save(out_p, quality=92)
    return out_p


def encode_vertical_mp4(frames: Sequence[Image.Image], wav_path: Path, out_mp4: Path) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
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
    err = proc.stderr.read() if proc.stderr else b""
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg failed ({ret}): {err.decode('utf-8', errors='replace')}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="What If EP.01: 如果你有 SCOUT 3D (9:16 3D Short)")
    parser.add_argument("--force", action="store_true", help="Force full 3D clean-plate re-render.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Skip thumbnail export on fast subtitle swap.")
    args = parser.parse_args()

    t_all = time.time()
    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_frames, _ = get_or_render_3d_plates(force=args.force)

    t_ov = time.time()
    final_frames = [
        overlay_scout3d_ui_and_subtitles(im, idx, SUBTITLE_LINES, SERIES_BADGE)
        for idx, im in enumerate(clean_frames)
    ]
    print(f"[scout3d] Post-process UI & Cantonese subtitles overlaid in {time.time() - t_ov:.2f}s.")

    wav_path = REPO_ROOT / ".cache" / "audio" / "whatif_scout3d.wav"
    if args.force or not wav_path.exists():
        synthesize_scout3d_audio(wav_path, duration_sec=TOTAL_FRAMES / float(FPS))

    out_mp4 = output_dir / "whatif_ep01_scout3d.mp4"
    encode_vertical_mp4(final_frames, wav_path, out_mp4)
    print(f"[scout3d] Encoded 9:16 MP4 -> {out_mp4} ({out_mp4.stat().st_size / 1024:.1f} KB) in {time.time() - t_all:.2f}s.")

    if not args.fast_sub_only:
        cs_path = export_scout3d_contact_sheet(final_frames, output_dir)
        print(f"[scout3d] Exported 276 frame thumbnails & contact sheet -> {cs_path}")


if __name__ == "__main__":
    main()
