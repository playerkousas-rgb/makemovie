"""Universal SCOUT 3D Episode Runner & Reusable Shot Library (`scout3d_runner.py`).

Supports two zero-friction workflows on Windows / macOS / Linux:
1. Direct paste into CMD (NO Git upload or extra script file needed):
     python src/scout3d_runner.py --b64 <BASE64_UTF8_JSON>
2. Standalone Git-tracked episode script (`episodes/epXX_*.py`) with `SUBTITLE_LINES` at line 1:
     python episodes/ep02_camp_eve.py
     python episodes/ep02_camp_eve.py --fast-sub-only
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from camera import clamp, lerp, smoothstep
from engine3d import Camera3D, Scene3D, hex_rgb01, v3
from scout3d_characters import (
    COL,
    SECTION_STYLES,
    draw_camp_tent,
    draw_handbook_stack,
    draw_leader_figure,
    draw_mom_figure,
    draw_scout_figure,
    draw_turntable_pedestal,
)
from spec_loader import ensure_font_path

ASPECT_PRESETS: Dict[str, Tuple[int, int]] = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (960, 960),
}

PRESET_CATALOG: Dict[str, str] = {
    "disaster_wrong_badges": "查書頭暈＋聯錯章俾領袖鬧（紅 ✕ 警告）",
    "scout3d_auto_snap": "SCOUT 3D 撳章自動上身＋方塊變波波流線（連頂部 UI 卡）",
    "mom_turntable_sew": "媽媽推開厚書・望住旋轉 3D 人仔輕鬆照聯",
    "dual_salute_praise": "方塊＋波波童軍齊敬三指禮・領袖豎拇指大讚（綠 ✓）",
    "section_parade": "多支部童軍同台轉身敬禮（升團／支部大曬冷）",
    "camp_eve_ready": "戶外營地帳篷前・童軍齊章揮手敬禮出發",
    "turntable_360_closeup": "360° 旋轉特寫・前後左右袖章與專章帶零死角",
    "mom_and_kid_proud": "母子開心出門・媽媽安心微笑＋童軍精神敬禮",
}

_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    fname = "LXGWWenKaiTC-Medium.ttf" if bold else "Iansui-Regular.ttf"
    key = (fname, size)
    if key not in _FONT_CACHE:
        fp = ensure_font_path(fname)
        _FONT_CACHE[key] = ImageFont.truetype(str(fp), size)
    return _FONT_CACHE[key]


def _sanitize_text_for_font(text: str) -> str:
    """Replace unsupported dingbats/emojis with crisp CJK/ASCII equivalents."""
    replacements = {
        "✓": "・",
        "✔": "・",
        "✅": "・",
        "❌": "✕",
        "–": "－",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    f = _font(32)
    cleaned: List[str] = []
    for ch in text:
        if ch == "\n" or ch.isspace():
            cleaned.append(ch)
            continue
        try:
            m = f.getmask(ch)
            if m.size[0] > 0 and m.size[1] > 0:
                cleaned.append(ch)
        except Exception:
            continue
    return "".join(cleaned)


def _tokenize_cjk_ascii(line: str) -> List[str]:
    tokens: List[str] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i:].startswith("SCOUT 3D"):
            tokens.append("SCOUT 3D")
            i += len("SCOUT 3D")
        elif line[i:].startswith("SCOUT3D"):
            tokens.append("SCOUT3D")
            i += len("SCOUT3D")
        elif line[i].isascii() and (line[i].isalnum() or line[i] in "._-+×"):
            j = i + 1
            while j < n and line[j].isascii() and (line[j].isalnum() or line[j] in "._-+×"):
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
        raw_line = raw_line.strip()
        if not raw_line:
            continue
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
    return lines or [""]


def normalize_episode_spec(raw: Dict[str, Any], subtitle_override: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """Validate and fill safe defaults on an episode specification dict."""
    ep_id_raw = str(raw.get("episode_id") or "scout3d_custom_ep")
    ep_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", ep_id_raw).strip("_") or "scout3d_custom_ep"

    aspect = str(raw.get("aspect") or "9:16")
    if aspect not in ASPECT_PRESETS:
        aspect = "9:16"
    width, height = ASPECT_PRESETS[aspect]

    fps = int(clamp(int(raw.get("fps") or 24), 12, 60))
    default_section = str(raw.get("section") or "scout")
    if default_section not in SECTION_STYLES:
        default_section = "scout"
    default_gender = "F" if str(raw.get("gender") or "M").upper() == "F" else "M"
    hero_style = "blocky" if str(raw.get("hero_style") or "bobo") == "blocky" else "bobo"
    bgm_mood = str(raw.get("bgm_mood") or "comedy_to_hero")
    series_badge = _sanitize_text_for_font(str(raw.get("series_badge") or "如果系列 · 如果你有 SCOUT 3D"))

    ui_raw = raw.get("ui_card") or {}
    toggles_raw = ui_raw.get("toggles") or ["世界會員章", "旅條 · 區章", "小隊章", "專科章 ×12"]
    toggles = [_sanitize_text_for_font(str(x))[:14] for x in list(toggles_raw)[:4]]
    while len(toggles) < 4:
        toggles.append(["世界會員章", "旅條 · 區章", "小隊章", "專科章 ×12"][len(toggles)])

    ui_card = {
        "title": _sanitize_text_for_font(str(ui_raw.get("title") or "SCOUT3D · 撳章自動上身")),
        "toggles": toggles,
    }

    shots_in = raw.get("shots") or []
    if not shots_in:
        raise ValueError("Episode spec must contain at least 1 shot in `shots`.")

    shots_norm: List[Dict[str, Any]] = []
    cur_frame = 0
    for idx, sh in enumerate(shots_in, start=1):
        preset = str(sh.get("preset") or "scout3d_auto_snap")
        if preset not in PRESET_CATALOG:
            preset = "scout3d_auto_snap"
        dur = float(clamp(float(sh.get("duration") or 3.0), 1.2, 12.0))
        n_frames = max(12, int(round(dur * fps)))
        sec = str(sh.get("section") or default_section)
        if sec not in SECTION_STYLES:
            sec = default_section
        gen = "F" if str(sh.get("gender") or default_gender).upper() == "F" else "M"
        style_sh = str(sh.get("style_mode") or hero_style)
        if style_sh not in ("bobo", "blocky", "morph"):
            style_sh = "morph" if preset == "scout3d_auto_snap" else hero_style

        sub_txt = str(sh.get("subtitle") or "")
        if subtitle_override and idx in subtitle_override:
            sub_txt = str(subtitle_override[idx])

        trio = sh.get("trio_sections") or ["cub", "scout", "venture"]
        trio_clean = [s if s in SECTION_STYLES else "scout" for s in list(trio)[:3]]
        while len(trio_clean) < 3:
            trio_clean.append("scout")

        shots_norm.append(
            {
                "index": idx,
                "preset": preset,
                "duration": n_frames / float(fps),
                "start_frame": cur_frame,
                "end_frame": cur_frame + n_frames - 1,
                "num_frames": n_frames,
                "section": sec,
                "gender": gen,
                "style_mode": style_sh,
                "camera": str(sh.get("camera") or "auto"),
                "show_ui_card": bool(sh.get("show_ui_card", preset == "scout3d_auto_snap")),
                "trio_sections": trio_clean,
                "subtitle": _sanitize_text_for_font(sub_txt),
            }
        )
        cur_frame += n_frames

    return {
        "episode_id": ep_id,
        "series_badge": series_badge,
        "aspect": aspect,
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": cur_frame,
        "section": default_section,
        "gender": default_gender,
        "hero_style": hero_style,
        "bgm_mood": bgm_mood,
        "ui_card": ui_card,
        "shots": shots_norm,
    }


def _find_shot(spec: Dict[str, Any], frame_idx: int) -> Dict[str, Any]:
    for sh in spec["shots"]:
        if sh["start_frame"] <= frame_idx <= sh["end_frame"]:
            return sh
    return spec["shots"][-1]


def _cam_framing_scale(aspect: str) -> Tuple[float, float]:
    """Return (fov_scale, z_dist_scale) so wide/square/vertical frames keep all actors clear."""
    if aspect == "16:9":
        return (0.76, 0.84)
    if aspect == "1:1":
        return (0.88, 0.92)
    return (1.0, 1.0)


def render_shot_3d_frame(spec: Dict[str, Any], frame_idx: int) -> Image.Image:
    """Render one clean 3D frame (zero baked text) for any preset & aspect ratio."""
    W_px: int = spec["width"]
    H_px: int = spec["height"]
    fps: int = spec["fps"]
    aspect: str = spec["aspect"]
    fov_s, z_s = _cam_framing_scale(aspect)

    sh = _find_shot(spec, frame_idx)
    preset = sh["preset"]
    sec = sh["section"]
    gen = sh["gender"]
    hero_style = "blocky" if sh["style_mode"] == "blocky" else "bobo"
    sec_has_sash = 1.0 if sec in ("scout", "sea_scout", "air_scout") else 0.0

    t = frame_idx / float(fps)
    local_f = frame_idx - sh["start_frame"]
    u = local_f / float(max(1, sh["num_frames"] - 1))
    lt = local_f / float(fps)
    e = smoothstep(u)

    if preset == "disaster_wrong_badges":
        shake_x = math.sin(t * 26.0) * 0.032 * smoothstep((lt - 0.8) / 0.5) * (1.0 - smoothstep((u - 0.78) / 0.2))
        cam = Camera3D(
            pos=v3(lerp(0.0, 0.04, e) + shake_x, lerp(2.08, 1.96, e), lerp(8.45, 7.65, e) * z_s),
            target=v3(0.0, lerp(1.38, 1.44, e), 0.0),
            fov_deg=38.0 * fov_s,
            roll_deg=math.sin(t * 9.0) * 0.9 * (1.0 - 0.5 * u),
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#3B3348"), bg_bot=hex_rgb01("#63566E"),
            floor_y=0.0, floor_color=hex_rgb01("#574D63"),
            key_dir=(-0.45, 0.78, 0.55), rim_color=hex_rgb01("#FF9E9E"),
        )
        draw_mom_figure(sc, v3(-0.88, 0.0, -0.35), yaw_deg=22.0, scale=0.86, mood="dizzy", t_sec=t)
        draw_handbook_stack(sc, v3(-0.82, 0.0, 0.62), yaw_deg=18.0, scale=0.90)
        draw_scout_figure(
            sc, v3(-0.02, 0.0, 0.28),
            yaw_deg=math.sin(t * 7.5) * 6.0, scale=0.90,
            style_mode=hero_style, expression="nervous",
            salute=0.0, badge_mode="wrong", show_sash=0.0,
            section=sec, gender=gen, t_sec=t,
        )
        draw_leader_figure(sc, v3(0.86, 0.0, -0.15), yaw_deg=-24.0, scale=0.92, mood="scold", t_sec=t)
        return sc.render()

    if preset == "scout3d_auto_snap":
        target_y = 1.80 if (sh["show_ui_card"] and aspect == "9:16") else 1.56
        cam = Camera3D(
            pos=v3(lerp(0.10, -0.08, e), lerp(2.15, 2.00, e), lerp(6.95, 6.35, e) * z_s),
            target=v3(0.0, target_y, 0.0),
            fov_deg=36.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#8AC6F2"), bg_bot=hex_rgb01("#DCF0FC"),
            floor_y=0.0, floor_color=hex_rgb01("#CBE6F8"),
            key_dir=(-0.50, 0.72, 0.65), rim_color=hex_rgb01("#FFFFFF"),
        )
        ped_x = 0.28 if (sh["show_ui_card"] and aspect == "16:9") else 0.0
        draw_turntable_pedestal(sc, (ped_x, 0.0), y_top=0.14, radius=1.02)

        if u < 0.38:
            yaw = lerp(-8.0, 42.0, smoothstep(u / 0.38))
        elif u < 0.68:
            yaw = lerp(42.0, -34.0, smoothstep((u - 0.38) / 0.30))
        else:
            yaw = lerp(-34.0, 14.0, smoothstep((u - 0.68) / 0.32))

        dur_s = sh["duration"]
        prog_map = {
            "membership": clamp((lt - 0.06 * dur_s) / 0.30),
            "link_award": clamp((lt - 0.09 * dur_s) / 0.30),
            "troop_tape": clamp((lt - 0.17 * dur_s) / 0.30),
            "district": clamp((lt - 0.21 * dur_s) / 0.30),
            "patrol": clamp((lt - 0.29 * dur_s) / 0.30),
            "prof_sleeve_1": clamp((lt - 0.39 * dur_s) / 0.30),
            "prof_sleeve_2": clamp((lt - 0.42 * dur_s) / 0.30),
        }
        sash_vis = smoothstep((lt - 0.40 * dur_s) / 0.32) * sec_has_sash

        do_morph = sh["style_mode"] != "blocky"
        morph_u = 0.54
        mode = ("blocky" if u < morph_u else "bobo") if do_morph else "blocky"

        draw_scout_figure(
            sc, v3(ped_x, 0.14, 0.0),
            yaw_deg=yaw, scale=0.96,
            style_mode=mode, expression="happy",
            salute=0.0, badge_mode="animated",
            badge_progress=prog_map, show_sash=sash_vis,
            section=sec, gender=gen, t_sec=t,
        )
        if do_morph and (morph_u - 0.06) <= u <= (morph_u + 0.08):
            ru = (u - (morph_u - 0.06)) / 0.14
            ring_y = lerp(2.75, 0.20, ru)
            for k in range(16):
                ang = 2.0 * math.pi * k / 16.0 + lt * 8.0
                sc.add_sphere(
                    v3(ped_x + 0.72 * math.cos(ang), ring_y, 0.72 * math.sin(ang)),
                    0.052, COL["gold"], roughness=0.1, emissive=(0.55, 0.42, 0.08),
                )
        return sc.render()

    if preset == "mom_turntable_sew":
        cam = Camera3D(
            pos=v3(lerp(-0.06, 0.04, e), 1.96, lerp(7.65, 7.05, e) * z_s),
            target=v3(0.0, 1.40, 0.0),
            fov_deg=37.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#FCE6C9"), bg_bot=hex_rgb01("#FFF7EA"),
            floor_y=0.0, floor_color=hex_rgb01("#F2DEC0"),
            key_dir=(-0.48, 0.75, 0.60), rim_color=hex_rgb01("#FFF6D6"),
        )
        draw_handbook_stack(sc, v3(-0.98, 0.0, -0.75), yaw_deg=-26.0, scale=0.78)
        draw_mom_figure(sc, v3(-0.56, 0.0, 0.14), yaw_deg=22.0, scale=0.92, mood="happy", t_sec=t)
        sc.add_cylinder(v3(0.58, 0.0, 0.14), v3(0.58, 0.82, 0.14), 0.15, COL["pedestal_rim"], roughness=0.35)
        draw_turntable_pedestal(sc, (0.58, 0.14), y_top=0.92, radius=0.62)
        draw_scout_figure(
            sc, v3(0.58, 0.92, 0.14),
            yaw_deg=-25.0 + lt * 54.0, scale=0.56,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, t_sec=t,
        )
        for sp_i in range(4):
            ang = lt * 3.2 + sp_i * (math.pi * 0.5)
            sc.add_sphere(
                v3(0.58 + 0.56 * math.cos(ang), 1.66 + 0.16 * math.sin(ang * 2.0), 0.14 + 0.56 * math.sin(ang)),
                0.040, COL["gold"], roughness=0.1, emissive=(0.45, 0.36, 0.05),
            )
        return sc.render()

    if preset == "section_parade":
        sal_u = smoothstep((u - 0.25) / 0.30)
        cam = Camera3D(
            pos=v3(lerp(-0.08, 0.08, e), lerp(2.04, 1.94, e), lerp(9.35, 8.55, e) * z_s),
            target=v3(0.0, 1.42, 0.0),
            fov_deg=38.5 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#8AC6F2"), bg_bot=hex_rgb01("#EEF7FD"),
            floor_y=0.0, floor_color=hex_rgb01("#D5E9F8"),
            key_dir=(-0.45, 0.76, 0.62), rim_color=hex_rgb01("#FFF8DC"),
        )
        trio = sh["trio_sections"]
        xs = (-1.12, 0.0, 1.12)
        zs = (-0.22, 0.24, -0.22)
        yaws = (16.0, lerp(-18.0, 10.0, e), -16.0)
        scales = (0.78, 0.88, 0.78)
        draw_turntable_pedestal(sc, (0.0, 0.24), y_top=0.12, radius=0.68)
        for idx_p, (s_name, px, pz, pyaw, psc) in enumerate(zip(trio, xs, zs, yaws, scales)):
            draw_scout_figure(
                sc, v3(px, 0.12 if idx_p == 1 else 0.0, pz),
                yaw_deg=pyaw, scale=psc,
                style_mode=hero_style, expression="happy",
                salute=sal_u, badge_mode="correct",
                show_sash=1.0 if s_name == "scout" else 0.0,
                section=s_name, gender="F" if idx_p == 2 and gen == "F" else gen,
                t_sec=t,
            )
        return sc.render()

    if preset == "camp_eve_ready":
        sal_u = smoothstep((u - 0.35) / 0.28)
        wave_u = 1.0 - sal_u
        cam = Camera3D(
            pos=v3(lerp(-0.10, 0.06, e), lerp(2.05, 1.95, e), lerp(8.75, 7.95, e) * z_s),
            target=v3(0.0, 1.44, 0.0),
            fov_deg=38.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#7CC5E8"), bg_bot=hex_rgb01("#E9F7D9"),
            floor_y=0.0, floor_color=hex_rgb01("#9ED18B"),
            key_dir=(-0.42, 0.78, 0.58), rim_color=hex_rgb01("#FFF6CC"),
        )
        draw_camp_tent(sc, v3(-0.92, 0.0, -0.82), yaw_deg=20.0, scale=1.08)
        draw_scout_figure(
            sc, v3(-0.36, 0.0, 0.26),
            yaw_deg=10.0, scale=0.88,
            style_mode=hero_style, expression="happy",
            salute=sal_u, wave=wave_u,
            badge_mode="correct", show_sash=1.0 if sec == "scout" else 0.0,
            section=sec, gender=gen, t_sec=t,
        )
        draw_leader_figure(sc, v3(0.88, 0.0, -0.05), yaw_deg=-22.0, scale=0.88, mood="praise", t_sec=t)
        return sc.render()

    if preset == "turntable_360_closeup":
        cam = Camera3D(
            pos=v3(0.0, lerp(1.98, 1.90, e), lerp(6.35, 5.85, e) * z_s),
            target=v3(0.0, 1.56, 0.0),
            fov_deg=35.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#8AC6F2"), bg_bot=hex_rgb01("#DCF0FC"),
            floor_y=0.0, floor_color=hex_rgb01("#CBE6F8"),
            key_dir=(-0.50, 0.72, 0.65), rim_color=hex_rgb01("#FFFFFF"),
        )
        draw_turntable_pedestal(sc, (0.0, 0.0), y_top=0.14, radius=1.04)
        draw_scout_figure(
            sc, v3(0.0, 0.14, 0.0),
            yaw_deg=lerp(-20.0, 340.0, e), scale=0.98,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, t_sec=t,
        )
        return sc.render()

    if preset == "mom_and_kid_proud":
        sal_u = smoothstep(lt / 0.50)
        cam = Camera3D(
            pos=v3(lerp(-0.05, 0.05, e), 1.98, lerp(7.85, 7.20, e) * z_s),
            target=v3(0.0, 1.44, 0.0),
            fov_deg=37.5 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, cam,
            bg_top=hex_rgb01("#FDE2B8"), bg_bot=hex_rgb01("#FFF8EC"),
            floor_y=0.0, floor_color=hex_rgb01("#F1DCB8"),
            key_dir=(-0.46, 0.76, 0.60), rim_color=hex_rgb01("#FFF7D6"),
        )
        draw_mom_figure(sc, v3(-0.62, 0.0, 0.05), yaw_deg=20.0, scale=0.92, mood="happy", t_sec=t)
        draw_turntable_pedestal(sc, (0.52, 0.20), y_top=0.13, radius=0.68)
        draw_scout_figure(
            sc, v3(0.52, 0.13, 0.20),
            yaw_deg=-12.0, scale=0.88,
            style_mode=hero_style, expression="happy",
            salute=sal_u, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, t_sec=t,
        )
        return sc.render()

    # Default / "dual_salute_praise":
    salute_u = smoothstep(lt / 0.45)
    cam = Camera3D(
        pos=v3(0.0, lerp(2.06, 1.96, e), lerp(8.75, 7.95, e) * z_s),
        target=v3(0.0, lerp(1.42, 1.48, e), 0.0),
        fov_deg=38.5 * fov_s,
    )
    sc = Scene3D(
        W_px, H_px, cam,
        bg_top=hex_rgb01("#7EC4CF"), bg_bot=hex_rgb01("#E8F8F5"),
        floor_y=0.0, floor_color=hex_rgb01("#CDEAE5"),
        key_dir=(-0.45, 0.76, 0.62), rim_color=hex_rgb01("#FFF8DC"),
    )
    draw_scout_figure(
        sc, v3(-0.98, 0.0, -0.18),
        yaw_deg=15.0, scale=0.82,
        style_mode="blocky", expression="happy",
        salute=salute_u, badge_mode="correct", show_sash=sec_has_sash,
        section=sec, gender=gen, t_sec=t,
    )
    draw_turntable_pedestal(sc, (-0.02, 0.28), y_top=0.13, radius=0.70)
    draw_scout_figure(
        sc, v3(-0.02, 0.13, 0.28),
        yaw_deg=8.0, scale=0.88,
        style_mode="bobo", expression="happy",
        salute=salute_u, badge_mode="correct", show_sash=sec_has_sash,
        section=sec, gender=gen, t_sec=t,
    )
    draw_leader_figure(sc, v3(0.90, 0.0, -0.06), yaw_deg=-20.0, scale=0.88, mood="praise", t_sec=t)
    return sc.render()


def overlay_episode_ui_and_subtitles(clean_img: Image.Image, spec: Dict[str, Any], frame_idx: int) -> Image.Image:
    """Overlay crisp vector UI & Cantonese subtitles onto a clean 3D plate."""
    W_px: int = spec["width"]
    H_px: int = spec["height"]
    fps: int = spec["fps"]
    aspect: str = spec["aspect"]
    sh = _find_shot(spec, frame_idx)
    local_f = frame_idx - sh["start_frame"]
    lt = local_f / float(fps)
    u = local_f / float(max(1, sh["num_frames"] - 1))

    out = clean_img.convert("RGBA")
    ui_layer = Image.new("RGBA", (W_px, H_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui_layer)

    # 1. Top Series Header Pill
    series_badge = spec["series_badge"]
    if series_badge:
        tag_sz = 25 if aspect == "9:16" else 22
        f_tag = _font(tag_sz, bold=True)
        tb = draw.textbbox((0, 0), series_badge, font=f_tag)
        tw_tag, th_tag = tb[2] - tb[0], tb[3] - tb[1]
        py0 = 56 if aspect == "9:16" else 24
        py1 = py0 + th_tag + 20
        px0 = W_px // 2 - tw_tag // 2 - 24
        px1 = W_px // 2 + tw_tag // 2 + 24
        draw.rounded_rectangle((px0, py0 + 3, px1, py1 + 3), radius=24, fill=(18, 28, 45, 110))
        is_warn = sh["preset"] == "disaster_wrong_badges"
        pill_bg = (198, 48, 56, 232) if is_warn else (31, 48, 82, 232)
        draw.rounded_rectangle((px0, py0, px1, py1), radius=24, fill=pill_bg, outline=(255, 255, 255, 210), width=2)
        draw.text((W_px // 2 - tw_tag // 2 - tb[0], (py0 + py1) // 2 - th_tag // 2 - tb[1]), series_badge, font=f_tag, fill=(255, 255, 255, 255))

    # 2. Interactive SCOUT 3D Toggle Banner Card (when enabled on shot)
    if sh["show_ui_card"]:
        if aspect == "16:9":
            card_x0, card_y0, card_x1, card_y1 = 32, 84, 510, 246
        elif aspect == "1:1":
            card_x0, card_y0, card_x1, card_y1 = 80, 84, W_px - 80, 244
        else:
            card_x0, card_y0, card_x1, card_y1 = 36, 122, W_px - 36, 286

        draw.rounded_rectangle((card_x0, card_y0 + 5, card_x1, card_y1 + 5), radius=20, fill=(20, 35, 60, 60))
        draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=20, fill=(255, 255, 255, 238), outline=(206, 224, 242, 255), width=2)

        f_hdr = _font(19 if aspect == "16:9" else 20, bold=True)
        f_row = _font(17 if aspect == "16:9" else 19, bold=False)
        hdr_txt = spec["ui_card"]["title"]
        draw.text((card_x0 + 18, card_y0 + 13), hdr_txt, font=f_hdr, fill=(31, 48, 82, 255))

        is_bobo_now = (sh["style_mode"] != "blocky") and (u >= 0.54)
        mode_txt = "外觀：波波流線" if is_bobo_now else "外觀：簡約方塊"
        mb = draw.textbbox((0, 0), mode_txt, font=f_row)
        mw = mb[2] - mb[0]
        extra_chk = 22 if is_bobo_now else 0
        mx1 = card_x1 - 14
        mx0 = mx1 - mw - 26 - extra_chk
        my0, my1 = card_y0 + 9, card_y0 + 43
        m_fill = (38, 166, 98, 245) if is_bobo_now else (62, 80, 112, 235)
        draw.rounded_rectangle((mx0, my0, mx1, my1), radius=15, fill=m_fill)
        draw.text((mx0 + 13 - mb[0], my0 + 6 - mb[1]), mode_txt, font=f_row, fill=(255, 255, 255, 255))
        if is_bobo_now:
            cx_k, cy_k = mx1 - 18, (my0 + my1) // 2 + 1
            draw.line([(cx_k - 6, cy_k), (cx_k - 1, cy_k + 5), (cx_k + 7, cy_k - 5)], fill=(255, 255, 255, 255), width=3)

        draw.line([(card_x0 + 16, card_y0 + 51), (card_x1 - 16, card_y0 + 51)], fill=(228, 236, 245, 255), width=2)

        trig_fracs = (0.06, 0.17, 0.29, 0.40)
        col_w = (card_x1 - card_x0 - 36) // 2
        for idx_t, (tf, label) in enumerate(zip(trig_fracs, spec["ui_card"]["toggles"])):
            r_grid, c_grid = idx_t // 2, idx_t % 2
            gx = card_x0 + 18 + c_grid * (col_w + 12)
            gy = card_y0 + 62 + r_grid * 50
            is_on = u >= tf
            draw.text((gx, gy + 5), label, font=f_row, fill=(32, 44, 64, 255) if is_on else (135, 145, 160, 255))
            tx1 = gx + col_w - 10
            tx0 = tx1 - 46
            ty0, ty1 = gy + 4, gy + 29
            draw.rounded_rectangle((tx0, ty0, tx1, ty1), radius=13, fill=(242, 121, 28, 255) if is_on else (204, 212, 222, 255))
            kx = tx1 - 12 if is_on else tx0 + 12
            ky = (ty0 + ty1) // 2
            draw.ellipse((kx - 9, ky - 9, kx + 9, ky + 9), fill=(255, 255, 255, 255))

    # 3. Bottom Subtitle Card
    sub_text = sh["subtitle"].strip()
    if sub_text:
        sub_sz = 33 if aspect == "9:16" else (29 if aspect == "1:1" else 28)
        f_sub = _font(sub_sz, bold=True)
        max_sub_w = W_px - (104 if aspect == "9:16" else 160)
        wrapped = _wrap_text_to_width(draw, sub_text, f_sub, max_w=max_sub_w)

        pop_offset = int(round((1.0 - min(1.0, local_f / 4.0)) * 12.0))
        line_bboxes = [draw.textbbox((0, 0), ln, font=f_sub) for ln in wrapped]
        line_ws = [bb[2] - bb[0] for bb in line_bboxes]
        line_hs = [bb[3] - bb[1] for bb in line_bboxes]
        line_gap = 11
        block_w = max(line_ws)
        block_h = sum(line_hs) + line_gap * (len(wrapped) - 1)

        base_cy = (H_px - 204) if aspect == "9:16" else ((H_px - 126) if aspect == "1:1" else (H_px - 88))
        cy_sub = base_cy + pop_offset
        pad_x, pad_y = 30, 18
        bx0 = W_px // 2 - block_w // 2 - pad_x
        bx1 = W_px // 2 + block_w // 2 + pad_x
        by0 = cy_sub - block_h // 2 - pad_y
        by1 = cy_sub + block_h // 2 + pad_y

        is_warn = sh["preset"] == "disaster_wrong_badges"
        accent_border = (255, 112, 112, 245) if is_warn else (247, 201, 66, 250)
        draw.rounded_rectangle((bx0, by0 + 6, bx1, by1 + 6), radius=22, fill=(12, 18, 30, 120))
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=22, fill=(22, 31, 48, 236), outline=accent_border, width=3)

        cur_y = cy_sub - block_h // 2
        for ln, bb, lw, lh in zip(wrapped, line_bboxes, line_ws, line_hs):
            tx = W_px // 2 - lw // 2 - bb[0]
            ty = cur_y - bb[1]
            draw.text((tx + 2, ty + 2), ln, font=f_sub, fill=(12, 16, 26, 240))
            txt_col = (255, 246, 210, 255) if ("SCOUT 3D" in ln or "SCOUT3D" in ln) else (255, 255, 255, 255)
            draw.text((tx, ty), ln, font=f_sub, fill=txt_col)
            cur_y += lh + line_gap

    return Image.alpha_composite(out, ui_layer).convert("RGB")


def synthesize_episode_audio(spec: Dict[str, Any], out_wav: Path) -> Path:
    """Synthesize shot-synced stereo 44.1kHz BGM + UI pop chimes + finale fanfare."""
    sr = 44100
    fps = float(spec["fps"])
    duration_sec = spec["total_frames"] / fps
    n = max(1, int(round(duration_sec * sr)))
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
            env = np.minimum(1.0, lt / 0.02) * np.exp(-lt * np.float32(1.8)) * np.minimum(1.0, np.maximum(0.0, dur - lt) / 0.04)
            sig = (0.75 * np.sin(2 * math.pi * freq * lt) + 0.25 * np.sin(4 * math.pi * freq * lt)) * env
        elif kind == "buzz":
            env = np.minimum(1.0, lt / 0.01) * np.exp(-lt * 3.5)
            sig = np.tanh(2.5 * np.sin(2 * math.pi * freq * lt) + 1.2 * np.sin(2 * math.pi * (freq * 1.06) * lt)) * env * 0.5
        else:
            env = np.minimum(1.0, lt / 0.004) * np.exp(-lt * 12.0)
            sig = np.sin(2 * math.pi * freq * lt) * env
        left[i0:i1] += sig * amp * math.sqrt(0.5 * (1.0 - pan))
        right[i0:i1] += sig * amp * math.sqrt(0.5 * (1.0 + pan))

    major_loop = [60, 64, 67, 69, 67, 64, 65, 69, 72, 74, 72, 67]
    for sh in spec["shots"]:
        st0 = sh["start_frame"] / fps
        dur_s = sh["duration"]
        preset = sh["preset"]
        if preset == "disaster_wrong_badges":
            minor_seq = [62, 65, 68, 67, 65, 62, 60, 62]
            step = 0.40
            k = 0
            while k * step < dur_s - 0.15:
                note(st0 + 0.08 + k * step, 0.34, m2f(minor_seq[k % len(minor_seq)]), 0.21, pan=-0.1, kind="pluck")
                k += 1
            note(st0 + min(dur_s * 0.52, dur_s - 0.35), 0.36, m2f(49), 0.25, pan=0.25, kind="buzz")
        else:
            # Bright chord shimmer at start of first upbeat shot
            for idx_c, semi in enumerate((60, 64, 67, 72)):
                note(st0 + idx_c * 0.04, 0.48, m2f(semi), 0.16, pan=0.0, kind="warm")
            if preset == "scout3d_auto_snap":
                for idx_b, tf in enumerate((0.06, 0.17, 0.29, 0.40)):
                    trig = st0 + tf * dur_s
                    note(trig, 0.16, m2f(76 + idx_b * 2), 0.25, pan=0.2, kind="pluck")
                    note(trig + 0.07, 0.18, m2f(84 + idx_b * 2), 0.21, pan=0.15, kind="pop")
                if sh["style_mode"] != "blocky":
                    mt = st0 + 0.50 * dur_s
                    for k_m, md in enumerate((67, 71, 74, 79, 83, 86)):
                        note(mt + k_m * 0.05, 0.34, m2f(md), 0.17, pan=(k_m - 2.5) * 0.12, kind="pluck")

            step = 0.48
            k = 0
            while k * step < dur_s - 0.20:
                md = major_loop[(sh["index"] * 3 + k) % len(major_loop)]
                note(st0 + 0.15 + k * step, 0.42, m2f(md), 0.17, pan=-0.12, kind="pluck")
                note(st0 + 0.15 + k * step, 0.40, m2f(md - 12), 0.14, pan=0.10, kind="warm")
                k += 1

    # Triumphant ending chord on final shot
    end_chord_t = max(0.1, duration_sec - 0.95)
    for semi in (60, 64, 67, 72, 76):
        note(end_chord_t, 0.85, m2f(semi), 0.19, pan=0.0, kind="warm")

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


def _compute_clean_plate_hash(spec: Dict[str, Any]) -> str:
    """Hash only 3D geometry parameters (excluding subtitles/UI text!) so subtitle edits hit cache."""
    h = hashlib.sha256()
    for fname in ("engine3d.py", "scout3d_characters.py"):
        h.update((SRC_DIR / fname).read_bytes())
    geom_spec = {
        "aspect": spec["aspect"],
        "width": spec["width"],
        "height": spec["height"],
        "fps": spec["fps"],
        "shots": [
            {
                "preset": s["preset"],
                "num_frames": s["num_frames"],
                "section": s["section"],
                "gender": s["gender"],
                "style_mode": s["style_mode"],
                "show_ui_card": s["show_ui_card"],
                "trio_sections": s["trio_sections"],
            }
            for s in spec["shots"]
        ],
    }
    h.update(json.dumps(geom_spec, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _worker_render_runner_frame(args: Tuple[Dict[str, Any], int, str]) -> int:
    spec, f_idx, out_png = args
    im = render_shot_3d_frame(spec, f_idx)
    im.save(out_png, format="PNG", compress_level=1)
    return f_idx


def export_episode_contact_sheet(frames: Sequence[Image.Image], spec: Dict[str, Any], output_dir: Path) -> Path:
    ep_id = spec["episode_id"]
    fps = float(spec["fps"])
    aspect = spec["aspect"]
    tw, th = (180, 320) if aspect == "9:16" else ((240, 135) if aspect == "16:9" else (200, 200))

    thumbs = [im.resize((tw, th), resample=Image.Resampling.LANCZOS) for im in frames]
    n_tiles = min(24, len(thumbs))
    cols = 6
    rows = int(math.ceil(n_tiles / float(cols)))
    pad, lh = 8, 22
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lh + pad) + pad), (24, 30, 42))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    idxs = [min(len(thumbs) - 1, round(i * (len(thumbs) - 1) / float(max(1, n_tiles - 1)))) for i in range(n_tiles)]
    for slot, f_idx in enumerate(idxs):
        r, c = slot // cols, slot % cols
        x, y = pad + c * (tw + pad), pad + r * (th + lh + pad)
        sheet.paste(thumbs[f_idx], (x, y))
        sh = _find_shot(spec, f_idx)
        draw.text((x + 4, y + th + 4), f"F{f_idx:03d} {f_idx/fps:4.1f}s S{sh['index']}", fill=(235, 242, 250), font=font)

    out_p = output_dir / f"contact_sheet_{ep_id}.jpg"
    sheet.save(out_p, quality=92)
    return out_p


def encode_episode_mp4(frames: Sequence[Image.Image], spec: Dict[str, Any], wav_path: Path, out_mp4: Path) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{spec['width']}x{spec['height']}",
        "-pix_fmt", "rgb24",
        "-r", str(spec["fps"]),
        "-i", "-",
        "-i", str(wav_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
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


def generate_standalone_py_source(raw_spec: Dict[str, Any]) -> str:
    """Generate a clean Git-ready `episodes/<episode_id>.py` script with SUBTITLE_LINES at line 1."""
    spec = normalize_episode_spec(raw_spec)
    sub_entries = ",\n".join(f"    {sh['index']}: {json.dumps(sh['subtitle'], ensure_ascii=False)}" for sh in spec["shots"])
    spec_copy = dict(raw_spec)
    spec_json_pretty = json.dumps(spec_copy, ensure_ascii=False, indent=4)
    return f'''SUBTITLE_LINES = {{
{sub_entries},
}}
SERIES_BADGE = {json.dumps(spec["series_badge"], ensure_ascii=False)}

"""SCOUT 3D Episode Script — {spec["episode_id"]}
Generated by SCOUT 3D 動畫劇本生成器 (makemovie)
Run directly in CMD:
    python episodes/{spec["episode_id"]}.py
Fast subtitle-only update (~1.5s via 3D clean-plate cache):
    python episodes/{spec["episode_id"]}.py --fast-sub-only
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from scout3d_runner import cli_run_from_episode_script

EPISODE_SPEC = json.loads(r"""
{spec_json_pretty}
""")

if __name__ == "__main__":
    EPISODE_SPEC["series_badge"] = SERIES_BADGE
    cli_run_from_episode_script(EPISODE_SPEC, SUBTITLE_LINES)
'''


def run_episode_dict(
    raw_spec: Dict[str, Any],
    subtitle_override: Optional[Dict[int, str]] = None,
    force: bool = False,
    fast_sub_only: bool = False,
    out_mp4_override: Optional[Path] = None,
) -> Path:
    """Render an episode dict end-to-end and return the path to the generated MP4."""
    t_all = time.time()
    spec = normalize_episode_spec(raw_spec, subtitle_override=subtitle_override)
    ep_id = spec["episode_id"]
    total = spec["total_frames"]

    plate_hash = _compute_clean_plate_hash(spec)
    plate_dir = REPO_ROOT / ".cache" / f"plates_{ep_id}_{plate_hash}"
    plate_dir.mkdir(parents=True, exist_ok=True)
    manifest = plate_dir / "manifest.json"

    cache_hit = (
        not force
        and manifest.exists()
        and all((plate_dir / f"plate_{i:04d}.png").exists() for i in range(total))
    )
    if cache_hit:
        print(f"[scout3d-runner] CACHE HIT ({plate_hash}): Reusing {total} clean 3D frames!")
    else:
        t0 = time.time()
        workers = min(max(1, (os.cpu_count() or 2)), 8)
        print(f"[scout3d-runner] Rendering '{ep_id}' — {total} frames @ {spec['width']}x{spec['height']} ({spec['fps']}fps) on {workers} CPU workers...")
        tasks = [(spec, i, str(plate_dir / f"plate_{i:04d}.png")) for i in range(total)]
        ctx = mp.get_context("spawn")
        step_log = max(1, total // 6)
        with ctx.Pool(processes=workers) as pool:
            for done_i, _ in enumerate(pool.imap_unordered(_worker_render_runner_frame, tasks, chunksize=6), 1):
                if done_i % step_log == 0 or done_i == total:
                    print(f"  [scout3d-runner] {done_i}/{total} 3D frames rendered...")
        manifest.write_text(json.dumps({"hash": plate_hash, "total_frames": total}, indent=2), encoding="utf-8")
        print(f"[scout3d-runner] Clean 3D plates finished in {time.time() - t0:.2f}s.")

    clean_frames: List[Image.Image] = []
    for i in range(total):
        with Image.open(plate_dir / f"plate_{i:04d}.png") as im:
            clean_frames.append(im.convert("RGB"))

    final_frames = [overlay_episode_ui_and_subtitles(im, spec, idx) for idx, im in enumerate(clean_frames)]

    wav_path = REPO_ROOT / ".cache" / "audio" / f"{ep_id}_{plate_hash}.wav"
    if force or not wav_path.exists():
        synthesize_episode_audio(spec, wav_path)

    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_mp4_override or (output_dir / f"{ep_id}.mp4")
    encode_episode_mp4(final_frames, spec, wav_path, out_mp4)
    print(f"[scout3d-runner] MP4 ready -> {out_mp4} ({out_mp4.stat().st_size / 1024:.1f} KB) in {time.time() - t_all:.2f}s.")

    if not fast_sub_only:
        cs = export_episode_contact_sheet(final_frames, spec, output_dir)
        print(f"[scout3d-runner] Contact sheet -> {cs}")

    return out_mp4


def cli_run_from_episode_script(raw_spec: Dict[str, Any], subtitle_lines: Dict[int, str]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=f"SCOUT 3D Episode: {raw_spec.get('episode_id', 'episode')}")
    parser.add_argument("--force", action="store_true", help="Force full 3D re-render ignoring clean-plate cache.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Fast subtitle swap (skip contact sheet).")
    parser.add_argument("--out", type=str, default="", help="Optional custom output .mp4 path.")
    args = parser.parse_args()
    out_p = Path(args.out) if args.out else None
    run_episode_dict(raw_spec, subtitle_override=subtitle_lines, force=args.force, fast_sub_only=args.fast_sub_only, out_mp4_override=out_p)


def decode_b64_spec(b64_str: str) -> Dict[str, Any]:
    pad = "=" * ((4 - len(b64_str.strip()) % 4) % 4)
    raw_bytes = base64.urlsafe_b64decode((b64_str.strip() + pad).encode("ascii"))
    return json.loads(raw_bytes.decode("utf-8"))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Universal SCOUT 3D Episode Runner — paste `--b64 <payload>` directly in Windows CMD or pass `--spec <file.json>`!"
    )
    parser.add_argument("--b64", type=str, default="", help="URL-safe or standard Base64 UTF-8 JSON episode payload (zero-file CMD execution!).")
    parser.add_argument("--spec", type=str, default="", help="Path to an episode .json spec file.")
    parser.add_argument("--write-py", action="store_true", help="Also save a Git-ready `episodes/<episode_id>.py` file locally.")
    parser.add_argument("--only-write-py", action="store_true", help="Only write `episodes/<episode_id>.py` without rendering video.")
    parser.add_argument("--force", action="store_true", help="Force full 3D clean-plate re-render.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Skip contact sheet generation.")
    parser.add_argument("--out", type=str, default="", help="Optional custom output MP4 path.")
    parser.add_argument("--list-presets", action="store_true", help="List available 3D shot presets and exit.")
    args = parser.parse_args()

    if args.list_presets:
        for k, desc in PRESET_CATALOG.items():
            print(f"  {k:24s} — {desc}")
        return

    if args.b64:
        # Accept both standard Base64 (+/) and URL-safe Base64 (-_)
        normalized_b64 = args.b64.strip().replace("+", "-").replace("/", "_")
        raw_spec = decode_b64_spec(normalized_b64)
    elif args.spec:
        raw_spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        parser.error("Provide either `--b64 <BASE64_JSON>` (paste directly in CMD) or `--spec <episode.json>`.")
        return

    if args.write_py or args.only_write_py:
        norm = normalize_episode_spec(raw_spec)
        ep_dir = REPO_ROOT / "episodes"
        ep_dir.mkdir(parents=True, exist_ok=True)
        py_path = ep_dir / f"{norm['episode_id']}.py"
        py_path.write_text(generate_standalone_py_source(raw_spec), encoding="utf-8")
        print(f"[scout3d-runner] Saved Git-ready episode script -> {py_path}")
        if args.only_write_py:
            return

    out_p = Path(args.out) if args.out else None
    run_episode_dict(raw_spec, force=args.force, fast_sub_only=args.fast_sub_only, out_mp4_override=out_p)


if __name__ == "__main__":
    main()
