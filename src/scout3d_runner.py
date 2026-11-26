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
import asyncio
import base64
import hashlib
import json
import math
import multiprocessing as mp
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import wave
import zlib
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
from engine3d import Camera3D, Scene3D, hex_rgb01, rot_x, rot_y, rot_z, v3
from scout3d_characters import (
    CHARACTER_PRESETS,
    COL,
    SECTION_STYLES,
    decode_s3d_code,
    draw_camp_tent,
    draw_campfire,
    draw_pine_tree,
    draw_handbook_stack,
    draw_leader_figure,
    draw_mom_figure,
    draw_scout_figure,
    draw_turntable_pedestal,
    resolve_character_preset,
)
from spec_loader import ensure_font_path

ASPECT_PRESETS: Dict[str, Tuple[int, int]] = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (960, 960),
}

PRESET_CATALOG: Dict[str, str] = {
    # --- General Scout STORY scenes (pure 3D storytelling, zero app promo) ---
    "story_arrival_meet": "童軍到達集會場地・遇見新同伴揮手打招呼",
    "story_group_chat": "小隊圍圈互相介紹・輕鬆傾偈交流",
    "story_leader_briefing": "領袖親切講解任務・童軍專心聆聽",
    "story_challenge_oops": "遇到難題／蝦碌一刻・緊張又搞笑",
    "story_camp_outdoors": "戶外營地帳篷與松樹・童軍齊齊準備",
    "story_team_task": "小隊合作完成任務・一人示範一人學習",
    "story_campfire_night": "夜晚營火會・火光映照一班童軍",
    "story_hero_closeup": "主角半身近鏡・制服與表情清楚動人",
    "story_happy_salute_end": "結尾齊齊三指敬禮・開心和諧收結",
    # --- SCOUT 3D app / uniform scenes (GitHub project promo mode) ---
    "disaster_wrong_badges": "查書頭暈＋聯錯章俾領袖鬧（紅 ✕ 警告）",
    "scout3d_auto_snap": "SCOUT 3D 撳章自動上身＋方塊變波波流線（連頂部 UI 卡）",
    "closeup_chest_badges": "胸前與領巾近鏡特寫・清楚睇見胸袋徽章與旅巾配色",
    "closeup_right_sleeve": "右袖徽章大特寫・清楚睇見旅號條／地域章／區章／小隊章",
    "closeup_left_sleeve": "左袖與專章帶特寫・清楚睇見進度章與專科章排列",
    "leader_guide_explain": "領袖同台親切講解・指點制服徽章正確佩戴重點",
    "mom_turntable_sew": "媽媽推開厚書・望住旋轉 3D 人仔輕鬆照聯",
    "turntable_360_closeup": "360° 旋轉特寫・前後左右袖章與專章帶零死角",
    "camp_eve_ready": "戶外營地帳篷前・童軍齊章揮手敬禮出發",
    "mom_and_kid_proud": "母子開心出門・媽媽安心微笑＋童軍精神敬禮",
    "section_parade": "多支部童軍同台轉身敬禮（升團／支部大曬冷）",
    "dual_salute_praise": "方塊＋波波童軍齊敬三指禮・領袖豎拇指大讚（綠 ✓）",
}

# 運鏡（Camera move）目錄：可以交畀 AI 每鏡自己揀，也可以由用戶固定一個。
# `auto` = 跟隨場景 preset 原本嘅運鏡；其餘會喺 preset 機位之上再加一層鏡頭運動。
CAMERA_CATALOG: Dict[str, str] = {
    "auto": "跟隨場景預設運鏡（AI／場景原生）",
    "push_in": "慢推近：鏡頭慢慢靠近主角",
    "pull_out": "慢拉遠：由近拉開，交代環境",
    "pan_left": "向左橫移：鏡頭平移到左邊",
    "pan_right": "向右橫移：鏡頭平移到右邊",
    "tilt_up": "上搖：由身體慢慢搖上天空／臉",
    "orbit_left": "環繞左轉：圍住主角轉向左",
    "orbit_right": "環繞右轉：圍住主角轉向右",
    "crane_up": "升高俯瞰：鏡頭慢慢升起",
    "low_angle": "低角度仰拍：主角更有氣勢",
    "handheld": "手持跟拍：微微震動，紀實感",
}

_CAMERA_ALIASES: Dict[str, str] = {
    "none": "auto", "default": "auto", "preset": "auto", "自動": "auto", "跟場景": "auto",
    "push": "push_in", "pushin": "push_in", "zoomin": "push_in", "dollyin": "push_in",
    "推近": "push_in", "推鏡": "push_in", "前推": "push_in",
    "pull": "pull_out", "pullout": "pull_out", "zoomout": "pull_out", "dollyout": "pull_out",
    "拉遠": "pull_out", "後拉": "pull_out",
    "panleft": "pan_left", "left": "pan_left", "左移": "pan_left", "左搖": "pan_left",
    "panright": "pan_right", "right": "pan_right", "右移": "pan_right", "右搖": "pan_right",
    "tiltup": "tilt_up", "up": "tilt_up", "上搖": "tilt_up", "仰": "tilt_up",
    "orbitleft": "orbit_left", "circleleft": "orbit_left", "左環繞": "orbit_left",
    "orbitright": "orbit_right", "circleright": "orbit_right", "右環繞": "orbit_right",
    "crane": "crane_up", "rise": "crane_up", "升高": "crane_up", "俯瞰": "crane_up",
    "low": "low_angle", "lowangle": "low_angle", "仰拍": "low_angle", "低角度": "low_angle",
    "handheld": "handheld", "hand": "handheld", "shake": "handheld", "手持": "handheld",
}


def _norm_camera(value: Any) -> str:
    """Map loose AI / user camera wording (e.g. '慢推近', 'push') to a camera key."""
    if value is None:
        return "auto"
    key = re.sub(r"[\s\-]+", "_", str(value).strip().lower())
    if not key:
        return "auto"
    if key in CAMERA_CATALOG:
        return key
    compact = key.replace("_", "")
    if compact in CAMERA_CATALOG:
        return compact
    if key in _CAMERA_ALIASES:
        return _CAMERA_ALIASES[key]
    if compact in _CAMERA_ALIASES:
        return _CAMERA_ALIASES[compact]
    # 中文自由描述（例：「慢推近」「向左橫移」「升高俯瞰」）
    if "推" in key or "push" in key or "dolly" in key and "out" not in key:
        return "push_in"
    if "拉" in key or "pull" in key:
        return "pull_out"
    if "環繞" in key or "orbit" in key:
        return "orbit_left" if ("左" in key or "left" in key) else "orbit_right"
    if "左" in key:
        return "pan_left"
    if "右" in key:
        return "pan_right"
    if "上搖" in key or "仰" in key:
        return "tilt_up"
    if "升高" in key or "crane" in key or "俯瞰" in key:
        return "crane_up"
    if "低角度" in key or "low" in key:
        return "low_angle"
    if "手持" in key or "hand" in key:
        return "handheld"
    return "auto"


# ─────────────────────────────────────────────────────────────────────
# AI 自由場景積木（Scene kit）
# AI 可以唔止揀現成 preset，而係用「背景 kind ＋ 道具 props ＋ 色盤」自己砌場景。
# 例：飛出太空 → kind="space" + props=["stars","planet","rocket"] + float=true
# ─────────────────────────────────────────────────────────────────────
SCENE_KIND_CATALOG: Dict[str, str] = {
    "space": "太空：深色星空，角色可以漂浮",
    "sky": "高空／藍天白雲，角色可以飛翔",
    "sunset": "黃昏：橙紫天空、剪影感",
    "night": "夜晚：深藍星空、草地",
    "forest": "森林／營地：綠地松樹",
    "beach": "海灘：藍天、沙地、海邊",
    "snow": "雪地：白雪、松樹、飄雪",
    "city": "城市：黃昏天空、高樓霓虹",
    "indoor": "室內：暖色牆、木地板",
    "underwater": "海底：藍綠水色、珊瑚石、氣泡",
    "void": "虛空：純黑背景、聚光燈",
}

_SCENE_KIND_ALIASES: Dict[str, str] = {
    "outer_space": "space", "galaxy": "space", "宇宙": "space", "太空": "space", "星際": "space",
    "cloud": "sky", "clouds": "sky", "天空": "sky", "高空": "sky", "飛天": "sky",
    "sunset": "sunset", "dusk": "sunset", "黃昏": "sunset", "日落": "sunset",
    "night": "night", "夜晚": "night", "晚上": "night", "夜景": "night",
    "forest": "forest", "woods": "forest", "camp": "forest", "森林": "forest", "營地": "forest",
    "beach": "beach", "sea": "beach", "ocean": "beach", "海灘": "beach", "沙灘": "beach", "海邊": "beach",
    "snow": "snow", "snowy": "snow", "雪地": "snow", "雪山": "snow", "下雪": "snow",
    "city": "city", "urban": "city", "城市": "city", "都市": "city", "街頭": "city",
    "indoor": "indoor", "room": "indoor", "室內": "indoor", "房間": "indoor", "屋企": "indoor",
    "underwater": "underwater", "sea_floor": "underwater", "海底": "underwater", "水下": "underwater",
    "void": "void", "black": "void", "虛空": "void", "黑暗": "void",
}

PROP_CATALOG: Dict[str, str] = {
    "stars": "星星（閃爍）",
    "moon": "月亮",
    "planet": "有光環的行星",
    "rocket": "火箭（可以升空）",
    "satellite": "人造衛星",
    "asteroid": "隕石",
    "cloud": "雲朵",
    "tent": "露營帳篷",
    "campfire": "營火",
    "pine": "松樹",
    "palm": "棕櫚樹",
    "rock": "岩石",
    "crystal": "發光水晶",
    "snowman": "雪人",
    "balloon": "氣球",
    "building": "城市大樓",
    "streetlamp": "街燈",
    "book": "書本",
    "flag": "旗幟",
    "bubble": "氣泡",
}

_PROP_ALIASES: Dict[str, str] = {
    "star": "stars", "星空": "stars", "星": "stars",
    "月": "moon", "月球": "moon",
    "行星": "planet", "星球": "planet", "土星": "planet",
    "火箭": "rocket", "飛船": "rocket", "太空船": "rocket",
    "衛星": "satellite",
    "隕石": "asteroid", "流星": "asteroid",
    "雲": "cloud", "白雲": "cloud",
    "帳篷": "tent", "營": "tent",
    "營火": "campfire", "火": "campfire",
    "松樹": "pine", "樹": "pine",
    "棕櫚": "palm", "棕櫚樹": "palm", "椰子樹": "palm",
    "石": "rock", "岩石": "rock",
    "水晶": "crystal", "寶石": "crystal",
    "雪人": "snowman",
    "氣球": "balloon",
    "大樓": "building", "樓": "building", "建築": "building",
    "街燈": "streetlamp", "路燈": "streetlamp",
    "書": "book", "書本": "book",
    "旗": "flag", "旗幟": "flag",
    "氣泡": "bubble", "泡泡": "bubble",
}

_DEFAULT_SCENE_PROPS: Dict[str, List[str]] = {
    "space": ["stars", "planet"],
    "night": ["stars", "campfire"],
    "sky": ["cloud"],
    "forest": ["pine", "tent"],
    "beach": ["palm", "rock"],
    "snow": ["snowman", "pine"],
    "city": ["building", "streetlamp"],
    "underwater": ["bubble", "rock"],
}

_SCENE_STYLES: Dict[str, Dict[str, Any]] = {
    "space":       {"bg_top": "#05081A", "bg_bot": "#241A46", "floor": None,   "key": (-0.35, 0.70, 0.60), "rim": "#9CC4FF"},
    "sky":         {"bg_top": "#63ACE6", "bg_bot": "#EAF7FF", "floor": None,   "key": (-0.45, 0.78, 0.55), "rim": "#FFF8D8"},
    "sunset":      {"bg_top": "#F07A4E", "bg_bot": "#FFD9A0", "floor": "#7A5747", "key": (-0.55, 0.60, 0.55), "rim": "#FFB36B"},
    "night":       {"bg_top": "#101A38", "bg_bot": "#2C3350", "floor": "#26301F", "key": (-0.35, 0.62, 0.70), "rim": "#FFD08A"},
    "forest":      {"bg_top": "#8FD4F5", "bg_bot": "#EAF9DE", "floor": "#A8D894", "key": (-0.42, 0.78, 0.60), "rim": "#FFF7CC"},
    "beach":       {"bg_top": "#7CCBF0", "bg_bot": "#E8FBFF", "floor": "#E8D3A4", "key": (-0.40, 0.80, 0.55), "rim": "#FFF3C4"},
    "snow":        {"bg_top": "#B9DDF4", "bg_bot": "#F4FBFF", "floor": "#EAF3FA", "key": (-0.42, 0.74, 0.62), "rim": "#FFFFFF"},
    "city":        {"bg_top": "#2B2C55", "bg_bot": "#E58A6A", "floor": "#4C4A56", "key": (-0.48, 0.66, 0.58), "rim": "#FFB36B"},
    "indoor":      {"bg_top": "#F3E2C8", "bg_bot": "#E7CFAF", "floor": "#9C6B44", "key": (-0.45, 0.72, 0.60), "rim": "#FFE2A8"},
    "underwater":  {"bg_top": "#0C4E63", "bg_bot": "#2A9DB0", "floor": "#2E7D82", "key": (-0.30, 0.82, 0.55), "rim": "#7FF0E0"},
    "void":        {"bg_top": "#020204", "bg_bot": "#0B0B12", "floor": None,   "key": (-0.30, 0.70, 0.65), "rim": "#B9C6FF"},
}

_FRAMING_ALIASES = {
    "wide": "wide", "long": "wide", "far": "wide", "遠景": "wide", "全景": "wide", "大景": "wide",
    "medium": "medium", "mid": "medium", "中景": "medium", "半身": "medium",
    "closeup": "closeup", "close": "closeup", "near": "closeup", "特寫": "closeup", "近鏡": "closeup", "大特寫": "closeup",
}


def _norm_scene_kind(value: Any) -> Optional[str]:
    if value is None:
        return None
    key = re.sub(r"[\s\-]+", "_", str(value).strip().lower())
    if not key:
        return None
    if key in SCENE_KIND_CATALOG:
        return key
    return _SCENE_KIND_ALIASES.get(key) or _SCENE_KIND_ALIASES.get(key.replace("_", ""))


def _norm_prop(value: Any) -> Optional[str]:
    key = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
    if not key:
        return None
    key = key.split(":")[0]
    if key in PROP_CATALOG:
        return key
    return _PROP_ALIASES.get(key)


def _hex_or_none(value: Any) -> Optional[str]:
    col = str(value or "").strip()
    return col if re.match(r"^#[0-9a-fA-F]{6}$", col) else None


def _vec3_or(value: Any, default: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if isinstance(value, (int, float)):
        return (float(value),) * 3
    if isinstance(value, dict):
        try:
            return (float(value.get("x", default[0])), float(value.get("y", default[1])), float(value.get("z", default[2])))
        except (TypeError, ValueError):
            return default
    if isinstance(value, (list, tuple)) and value:
        try:
            if len(value) == 1:
                return (float(value[0]),) * 3
            return (float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else default[2])
        except (TypeError, ValueError):
            return default
    return default


_NO_OBJECT_SHAPES = {"sphere", "ellipsoid", "box", "capsule", "cylinder", "ring"}
_BLUEPRINT_SHAPE_ALIASES: Dict[str, str] = {
    "sphere": "sphere", "ball": "sphere", "球": "sphere", "圓球": "sphere", "星球": "sphere",
    "星": "sphere", "太陽": "sphere", "月亮": "sphere", "石頭": "sphere", "球體": "sphere",
    "ellipsoid": "ellipsoid", "橢球": "ellipsoid", "橢圓": "ellipsoid", "卵形": "ellipsoid", "蛋": "ellipsoid",
    "box": "box", "cube": "box", "方塊": "box", "盒": "box", "立方體": "box", "箱": "box",
    "capsule": "capsule", "膠囊": "capsule", "藥丸": "capsule",
    "cylinder": "cylinder", "柱": "cylinder", "圓柱": "cylinder", "柱體": "cylinder", "管": "cylinder",
    "ring": "ring", "環": "ring", "光環": "ring", "圈": "ring", "軌道": "ring", "土星環": "ring", "呼拉圈": "ring",
}


def _norm_shape(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    key = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
    if not key:
        return fallback
    if key in _NO_OBJECT_SHAPES:
        return key
    return _BLUEPRINT_SHAPE_ALIASES.get(key, fallback)


def _safe_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return max(lo, min(hi, float(default)))


def _norm_anim(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, str):
        value = {"kind": value}
    if not isinstance(value, dict):
        return None
    kind_raw = str(value.get("kind") or value.get("type") or "").strip().lower()
    kinds = {
        "bob": "bob", "float": "bob", "浮": "bob", "漂浮": "bob", "上下": "bob",
        "drift": "drift", "飄": "drift", "飄移": "drift",
        "spin": "spin", "rotate": "spin", "轉": "spin", "旋轉": "spin",
        "pulse": "pulse", "閃": "pulse", "呼吸": "pulse", "閃爍": "pulse",
        "none": "none", "still": "none",
    }
    kind = kinds.get(kind_raw)
    if not kind:
        return None
    try:
        amp = max(0.0, min(6.0, float(value.get("amp", value.get("amount", 0.12)))))
        speed = max(0.0, min(12.0, float(value.get("speed", 1.0))))
        phase = float(value.get("phase", 0.0))
    except (TypeError, ValueError):
        amp, speed, phase = 0.12, 1.0, 0.0
    return {"kind": kind, "amp": amp, "speed": speed, "phase": phase}


def _norm_repeat(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    try:
        count = int(max(1, min(80, int(value.get("count", value.get("n", 12))))))
    except (TypeError, ValueError):
        return None
    area_raw = value.get("area") or value.get("box") or value.get("range") or [[-3, 3], [0, 4], [-6, -2]]
    if isinstance(area_raw, dict):
        area = [
            (float(area_raw.get("x0", -3)), float(area_raw.get("x1", 3))),
            (float(area_raw.get("y0", 0)), float(area_raw.get("y1", 4))),
            (float(area_raw.get("z0", -6)), float(area_raw.get("z1", -2))),
        ]
    else:
        try:
            if isinstance(area_raw, (list, tuple)) and len(area_raw) == 6:
                area = [(float(area_raw[0]), float(area_raw[1])), (float(area_raw[2]), float(area_raw[3])), (float(area_raw[4]), float(area_raw[5]))]
            else:
                area = [
                    (float(area_raw[0][0]), float(area_raw[0][1])),
                    (float(area_raw[1][0]), float(area_raw[1][1])),
                    (float(area_raw[2][0]), float(area_raw[2][1])),
                ]
        except (TypeError, ValueError, IndexError):
            return None
    try:
        seed = int(value.get("seed", 17))
    except (TypeError, ValueError):
        seed = 17
    return {"count": count, "area": area, "seed": seed}


def _norm_blueprint_object(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    shape = _norm_shape(raw.get("shape") or raw.get("type") or raw.get("form"), "sphere")
    if not shape:
        return None
    pos = _vec3_or(raw.get("pos") or raw.get("position") or raw.get("at") or raw.get("center"), (0.0, 1.2, -3.0))
    pos = tuple(max(-40.0, min(40.0, c)) for c in pos)
    size = _vec3_or(raw.get("size") or raw.get("scale") or raw.get("radii") or raw.get("radius"), (0.5, 0.5, 0.5))
    size = tuple(max(0.01, min(20.0, abs(c))) for c in size)
    rot = _vec3_or(raw.get("rot") or raw.get("rotation"), (0.0, 0.0, 0.0))
    color = _hex_or_none(raw.get("color") or raw.get("colour")) or "#C9D4EA"
    try:
        glow = max(0.0, min(1.0, float(raw.get("glow", raw.get("emissive", 0.0)))))
        rough = max(0.05, min(1.0, float(raw.get("roughness", raw.get("rough", 0.5)))))
    except (TypeError, ValueError):
        glow, rough = 0.0, 0.5
    try:
        count = int(max(2, min(96, int(raw.get("count", 48)))))
    except (TypeError, ValueError):
        count = 48
    return {
        "shape": shape,
        "pos": pos,
        "size": size,
        "rot": rot,
        "color": color,
        "glow": glow,
        "rough": rough,
        "anim": _norm_anim(raw.get("anim") or raw.get("animation") or raw.get("motion")),
        "repeat": _norm_repeat(raw.get("repeat") or raw.get("copies") or raw.get("scatter")),
        "count": count,
        "tube": max(0.008, min(2.0, _safe_float(raw.get("tube"), size[1] if shape == "ring" else 0.12, 0.008, 2.0))),
        "axis": str(raw.get("axis") or "y").strip().lower()[:1] or "y",
        "bevel": max(0.0, min(2.0, _safe_float(raw.get("bevel"), min(size) * 0.2, 0.0, 2.0))),
    }


def _norm_scene(value: Any) -> Optional[Dict[str, Any]]:
    """Normalize an AI scene. Accepts the legacy kind/props kit *and* free-form blueprints.

    Blueprint form (AI can invent anything from engine primitives):
      {"objects": [{"shape": "ring", "pos": [-2, 3, -5], "size": [1.2, 0.12], "color": "#E3C48A"}],
       "sky": {"top": "#05081A", "bottom": "#241A46"}, "floor": false,
       "framing": "wide", "float": true, "cast": true}
    """
    if isinstance(value, str):
        kind = _norm_scene_kind(value)
        return {"kind": kind, "props": list(_DEFAULT_SCENE_PROPS.get(kind or "", [])), "objects": []} if kind else None
    if not isinstance(value, dict):
        return None

    kind = _norm_scene_kind(value.get("kind") or value.get("type") or value.get("backdrop") or value.get("place"))

    # ---- free-form objects / legacy props ----
    objects: List[Dict[str, Any]] = []
    props: List[str] = []
    raw_objects = value.get("objects")
    if isinstance(raw_objects, list):
        for item in raw_objects[:48]:
            if isinstance(item, dict):
                obj = _norm_blueprint_object(item)
                if obj:
                    objects.append(obj)
            elif isinstance(item, str):
                p = _norm_prop(item)
                if p and p not in props:
                    props.append(p)
    if not objects:
        raw_props = value.get("props") or value.get("items") or []
        if isinstance(raw_props, str):
            raw_props = re.split(r"[,、/|]+", raw_props)
        for item in list(raw_props)[:10]:
            p = _norm_prop(item)
            if p and p not in props:
                props.append(p)
    if not props and kind and not objects:
        props = list(_DEFAULT_SCENE_PROPS.get(kind, []))
    if not kind and not props and not objects:
        return None

    framing_raw = str(value.get("framing") or value.get("shot_size") or "").strip().lower()
    framing = _FRAMING_ALIASES.get(framing_raw, "medium")

    # ---- colours: palette / sky / background / floor / light ----
    palette: Dict[str, str] = {}
    palette_raw = value.get("palette") or {}
    if isinstance(palette_raw, dict):
        for src, dst in (("sky_top", "sky_top"), ("sky_bottom", "sky_bottom"), ("floor", "floor")):
            col = _hex_or_none(palette_raw.get(src))
            if col:
                palette[dst] = col
    sky_raw = value.get("sky") or value.get("background") or value.get("bg")
    if isinstance(sky_raw, str):
        col = _hex_or_none(sky_raw)
        if col:
            palette["sky_top"] = col
            palette["sky_bottom"] = col
    elif isinstance(sky_raw, dict):
        for src, dst in (("top", "sky_top"), ("sky_top", "sky_top"), ("bottom", "sky_bottom"), ("sky_bottom", "sky_bottom"), ("color", "sky_top")):
            col = _hex_or_none(sky_raw.get(src))
            if col:
                palette[dst] = col
    elif isinstance(sky_raw, (list, tuple)) and sky_raw:
        col = _hex_or_none(sky_raw[0])
        if col:
            palette["sky_top"] = col
        if len(sky_raw) > 1:
            col2 = _hex_or_none(sky_raw[1])
            if col2:
                palette["sky_bottom"] = col2

    floor_specified = any(k in value for k in ("floor", "ground"))
    floor_value: Any = None
    floor_y = 0.0
    floor_raw = value.get("floor", value.get("ground"))
    if floor_raw is False or floor_raw is None and floor_specified:
        floor_value = False
    elif isinstance(floor_raw, str):
        floor_value = _hex_or_none(floor_raw)
    elif isinstance(floor_raw, dict):
        floor_value = _hex_or_none(floor_raw.get("color") or floor_raw.get("colour"))
        try:
            floor_y = float(floor_raw.get("y", 0.0))
        except (TypeError, ValueError):
            floor_y = 0.0
    elif isinstance(floor_raw, (int, float)) and not isinstance(floor_raw, bool):
        floor_y = float(floor_raw)

    light_raw = value.get("light") or value.get("lights") or {}
    light: Dict[str, Any] = {}
    if isinstance(light_raw, dict):
        key_col = _hex_or_none(light_raw.get("key") or light_raw.get("key_color"))
        rim_col = _hex_or_none(light_raw.get("rim") or light_raw.get("rim_color"))
        if key_col:
            light["key_color"] = key_col
        if rim_col:
            light["rim"] = rim_col
        if "dir" in light_raw or "direction" in light_raw:
            light["dir"] = _vec3_or(light_raw.get("dir") or light_raw.get("direction"), (-0.4, 0.7, 0.6))

    float_raw = value.get("float", value.get("floating"))
    if float_raw is None:
        floaty = bool(kind in ("space", "void", "sky")) or floor_value is False
    else:
        floaty = bool(float_raw)

    scene: Dict[str, Any] = {
        "kind": kind or "",
        "props": props,
        "objects": objects,
        "framing": framing,
        "float": floaty,
        "palette": palette,
        "floor": floor_value,
        "floor_y": floor_y,
        "light": light,
        "cast": bool(value.get("cast", value.get("characters", True))),
    }
    return scene


_STORY_SECTION_ALIASES: Dict[str, str] = {
    "grasshopper": "grasshopper", "grasshoppers": "grasshopper", "小童軍": "grasshopper", "gh": "grasshopper",
    "cub": "cub", "cubs": "cub", "幼童軍": "cub",
    "scout": "scout", "scouts": "scout", "童軍": "scout",
    "seascout": "sea_scout", "sea_scout": "sea_scout", "sea": "sea_scout", "海童軍": "sea_scout",
    "airscout": "air_scout", "air_scout": "air_scout", "air": "air_scout", "空童軍": "air_scout",
    "venture": "venture", "ventures": "venture", "rover": "venture", "rovers": "venture", "深資童軍": "venture",
    "leader": "leader", "leaders": "leader", "成年領袖": "leader", "領袖": "leader",
}

_ROBOT_SKIN_ALIASES = ("ai_robot", "airobot", "robot", "ai", "bot", "機械人", "机器人", "機械童軍")


def _norm_story_section(value: Any) -> Optional[str]:
    """Map loose AI / user section wording (e.g. 'grasshopper', '小童軍') to a rig section key."""
    key = re.sub(r"[\s_\-]+", "", str(value or "").strip().lower())
    if not key:
        return None
    if key in _STORY_SECTION_ALIASES:
        return _STORY_SECTION_ALIASES[key]
    raw_key = str(value or "").strip().lower()
    return _STORY_SECTION_ALIASES.get(raw_key)


def _section_from_s3d(code: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the Scout section encoded inside a decoded S3D outfit code."""
    if not code:
        return None
    rsec = str(code.get("rigSection") or code.get("section") or "").lower().strip()
    rvar = str(code.get("variant") or "").lower().strip()
    if rsec == "scout" and rvar == "sea":
        return "sea_scout"
    if rsec == "scout" and rvar == "air":
        return "air_scout"
    if rsec == "rover":
        return "venture"
    return rsec if rsec in SECTION_STYLES else None


def _norm_actor_skin(value: Any) -> str:
    """Return 'ai_robot' when the episode protagonist is an AI / robot, else 'human'."""
    key = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
    if not key:
        return "human"
    if key in _ROBOT_SKIN_ALIASES or "robot" in key or "機械" in key or "机器人" in key:
        return "ai_robot"
    return "human"


CANTONESE_VOICES: Dict[str, str] = {
    "zh-HK-HiuMaanNeural": "曉曼（香港廣東話自然女聲）",
    "zh-HK-HiuGaaiNeural": "曉佳（香港廣東話輕快女聲）",
    "zh-HK-WanLungNeural": "雲龍（香港廣東話精神男聲）",
    "none": "純背景音樂（唔配人聲）",
}


_VOICE_ENGINES = ("edge", "piper", "coqui", "command")


def _norm_voice_engine(value: Any) -> str:
    key = str(value or "").strip().lower()
    aliases = {"edge-tts": "edge", "edgetts": "edge", "piper-tts": "piper", "coqui-tts": "coqui",
               "custom": "command", "cmd": "command", "shell": "command"}
    key = aliases.get(key, key)
    return key if key in _VOICE_ENGINES else "edge"


def _run_external_tts(engine: str, text: str, voice: str, model: str, command: str,
                      out_audio: Path) -> None:
    """Synthesize speech with a local/open-source engine, writing any audio format to out_audio."""
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    if engine == "piper":
        if not model:
            raise RuntimeError("piper 需要 voice_model（.onnx voice 路徑）")
        exe = os.environ.get("PIPER_BIN") or "piper"
        cmd = [exe, "--model", model, "--output_file", str(out_audio)]
        res = subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"piper failed ({res.returncode}): {res.stderr.decode('utf-8', 'ignore')[:200]}")
        return
    if engine == "coqui":
        try:
            from TTS.api import TTS  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("未安裝 Coqui TTS（pip install TTS）") from exc
        if not model:
            raise RuntimeError("coqui 需要 voice_model（例如 tts_models/zh-CN/... 或 Cantonese 模型）")
        kwargs = {"text": text, "file_path": str(out_audio)}
        try:
            api = TTS(model_name=model)
            api.tts_to_file(**kwargs)
        except TypeError:
            api = TTS(model_name=model)
            api.tts_to_file(text=text, file_path=str(out_audio), language="zh")
        return
    if engine == "command":
        if not command:
            raise RuntimeError("command 引擎需要 tts_command，例如：mytts --out {out} < {text_file}")
        import shlex
        tmp_txt = out_audio.with_suffix(out_audio.suffix + ".txt")
        tmp_txt.write_text(text, encoding="utf-8")
        cmd = command.replace("{out}", str(out_audio)).replace("{text_file}", str(tmp_txt)).replace("{voice}", voice)
        if "{text}" in cmd:
            cmd = cmd.replace("{text}", shlex.quote(text))
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        tmp_txt.unlink(missing_ok=True)
        if res.returncode != 0:
            raise RuntimeError(f"tts command failed ({res.returncode}): {res.stderr.decode('utf-8', 'ignore')[:300]}")
        return
    raise RuntimeError(f"unknown voice engine: {engine}")


def _clean_cantonese_tts_text(text: str) -> str:
    """Normalize Cantonese narration text so edge-tts speaks naturally without spelling symbols."""
    t = str(text or "").strip()
    if not t:
        return ""
    # Strip accidental speaker prefix like "旁白："
    t = re.sub(r"^(?:旁白|VO|Voiceover)\s*[:：]\s*", "", t, flags=re.IGNORECASE)
    # Mixed-case "Scout 3D" so neural TTS pronounces the word "Scout" instead of spelling S-C-O-U-T
    t = re.sub(r"SCOUT\s*3D", "Scout 3D", t, flags=re.IGNORECASE)
    t = t.replace("×", "乘").replace("✕", "").replace("✓", "").replace("✔", "")
    t = re.sub(r"[\r\n]+", "，", t)
    t = re.sub(r"(?:——|—|–|・|·|•|\|)+", "，", t)
    t = re.sub(r"[，、,\s]*[，、,]+[，、,\s]*", "，", t)
    t = t.strip(" ，、,")
    return t

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
    s3d_custom = decode_s3d_code(raw.get("s3d_code") or raw.get("s3d_custom"))
    ep_char_cfg = resolve_character_preset(raw.get("char_preset"))

    s3d_sec = None
    s3d_gen = None
    s3d_style = None
    if s3d_custom:
        rsec = str(s3d_custom.get("rigSection") or s3d_custom.get("section") or "").lower().strip()
        rvar = str(s3d_custom.get("variant") or "").lower().strip()
        if rsec == "scout" and rvar == "sea":
            s3d_sec = "sea_scout"
        elif rsec == "scout" and rvar == "air":
            s3d_sec = "air_scout"
        elif rsec == "rover":
            s3d_sec = "venture"
        elif rsec in SECTION_STYLES:
            s3d_sec = rsec
        if s3d_custom.get("gender"):
            s3d_gen = "F" if str(s3d_custom["gender"]).upper().startswith(("F", "G")) else "M"
        lk = str(s3d_custom.get("look") or "").lower()
        if lk in ("simple", "blocky"):
            s3d_style = "blocky"
        elif lk in ("smooth", "detailed", "bobo"):
            s3d_style = "bobo"

    # Story section: a pasted `S3D1_...` outfit code ALWAYS wins; otherwise follow the AI/user
    # `story_section` (e.g. "grasshopper") so a pure story is never hijacked by a promo preset.
    story_section = _norm_story_section(raw.get("story_section"))
    if s3d_sec:
        story_section = s3d_sec
    default_section = str(raw.get("section") or story_section or s3d_sec or ep_char_cfg.get("section") or "scout")
    if default_section not in SECTION_STYLES:
        default_section = "scout"
    ep_actor_skin = _norm_actor_skin(raw.get("actor_skin"))
    default_gender = "F" if str(raw.get("gender") or s3d_gen or ep_char_cfg.get("gender") or "M").upper() == "F" else "M"
    hero_style = "blocky" if str(raw.get("hero_style") or s3d_style or ep_char_cfg.get("style_mode") or "bobo") == "blocky" else "bobo"
    # A character preset only supplies hat/sash defaults when it belongs to the SAME Scout section,
    # so e.g. `ming_scout_sash` (Land Scout) never forces a hat/sash onto a Grasshopper story hero.
    preset_sec = str(ep_char_cfg.get("section") or "")
    preset_matches_section = (preset_sec == default_section)
    ep_cfg_hat = ep_char_cfg.get("hat", None) if preset_matches_section else None
    ep_cfg_sash = ep_char_cfg.get("show_sash", None) if preset_matches_section else None
    # 真實童軍制服本身有帽（小童軍藍帽／幼童軍帽／貝雷帽）；故事模式預設戴帽，
    # 但 AI／用戶可以喺 shot 或 episode 明確用 "hat": false 關掉。
    if _norm_story_section(raw.get("story_section")) and not s3d_custom and raw.get("hat") is None:
        ep_cfg_hat = True
    default_hat = raw.get("hat", s3d_custom.get("hat") if (s3d_custom and "hat" in s3d_custom) else ep_cfg_hat)
    default_sash = raw.get(
        "show_sash",
        (1.0 if s3d_custom.get("sash") else 0.0) if (s3d_custom and "sash" in s3d_custom) else ep_cfg_sash,
    )

    # ------------------------------------------------------------------
    # 角色陣容（1–5 人）：每個角色可以有自己的支部、真人／AI 機械人設定，
    # 以及自己嘅 SCOUT 3D 制服穿搭碼（S3D1_... / JSON）。
    # 冇 `characters` 嘅舊 spec 會自動變成單一主角，行為同以前完全一樣。
    # ------------------------------------------------------------------
    story_mode = bool(_norm_story_section(raw.get("story_section")) or raw.get("characters") or raw.get("cast"))
    cast_raw = raw.get("characters") or raw.get("cast")
    explicit_cast = isinstance(cast_raw, list) and len(cast_raw) > 0
    ep_cast: List[Dict[str, Any]] = []
    if explicit_cast:
        for i, item in enumerate(list(cast_raw)[:5]):
            c = item if isinstance(item, dict) else {"section": item}
            raw_ref = c.get("section") or c.get("story_section") or c.get("uniform")
            code_raw = c.get("s3d_code") or c.get("s3d_custom")
            uniform_code = c.get("uniform_code")
            if code_raw is None and isinstance(uniform_code, str) and uniform_code.strip().upper().startswith(("S3D", "{")):
                code_raw = uniform_code
            code = decode_s3d_code(code_raw)
            sec = (
                _norm_story_section(raw_ref)
                or _section_from_s3d(code)
                or _norm_story_section(uniform_code)
                or default_section
            )
            if sec not in SECTION_STYLES:
                sec = "scout"
            if "actor_skin" in c or "skin" in c:
                skin = _norm_actor_skin(c.get("actor_skin") or c.get("skin"))
            else:
                skin = ep_actor_skin if i == 0 else "human"
            c_gen = c.get("gender")
            if not c_gen and code and code.get("gender"):
                c_gen = code["gender"]
            if c_gen:
                gen_i = "F" if str(c_gen).upper().startswith(("F", "G")) else "M"
            elif sec == "leader":
                gen_i = "M"
            else:
                gen_i = default_gender if i == 0 else ("F" if i % 2 == 1 else "M")
            if "hat" in c:
                hat_i = bool(c["hat"])
            elif code and "hat" in code and code["hat"] is not None:
                hat_i = bool(code["hat"])
            elif i == 0 and default_hat is not None:
                hat_i = default_hat
            else:
                hat_i = True if story_mode else None
            if "show_sash" in c:
                sash_i = float(c["show_sash"])
            elif code and "sash" in code and code["sash"] is not None:
                sash_i = 1.0 if code["sash"] else 0.0
            else:
                sash_i = default_sash if i == 0 else None
            style_i = str(c.get("style_mode") or hero_style)
            ep_cast.append(_make_actor(
                sec, skin, gen_i, hat_i, sash_i, style_i, code,
                _sanitize_text_for_font(str(c.get("name") or f"角色{i + 1}"))[:12],
            ))
        hero0 = ep_cast[0]
        default_section = hero0["section"]
        ep_actor_skin = hero0["skin"]
        default_gender = hero0["gender"]
        hero_style = hero0["style_mode"] if hero0["style_mode"] in ("bobo", "blocky") else hero_style
        default_hat = hero0["hat"]
        default_sash = hero0["show_sash"]
    else:
        ep_cast = [_make_actor(
            default_section, ep_actor_skin, default_gender, default_hat, default_sash,
            hero_style, s3d_custom, "主角",
        )]

    default_camera = _norm_camera(raw.get("camera") or raw.get("camera_move") or raw.get("default_camera"))
    ep_scene = _norm_scene(raw.get("scene") or raw.get("world") or raw.get("set"))
    bgm_mood = str(raw.get("bgm_mood") or "comedy_to_hero")
    voice_raw = str(raw.get("voice") if raw.get("voice") is not None else "zh-HK-HiuMaanNeural").strip()
    if voice_raw.lower() in ("", "none", "off", "false", "mute"):
        voice = "none"
    elif voice_raw.lower() == "auto":
        voice = "zh-HK-HiuMaanNeural"
    else:
        voice = voice_raw
    voice_rate = str(raw.get("voice_rate") or "+6%").strip()
    if not re.match(r"^[+-]\d{1,3}%$", voice_rate):
        voice_rate = "+6%"
    voice_engine = _norm_voice_engine(raw.get("voice_engine") or raw.get("tts_engine"))
    voice_model = str(raw.get("voice_model") or raw.get("tts_model") or "").strip()
    tts_command = str(raw.get("tts_command") or raw.get("voice_command") or "").strip()
    series_badge = _sanitize_text_for_font(str(raw.get("series_badge") or "童軍動畫小劇場"))

    ui_raw = raw.get("ui_card") or {}
    fallback_toggles = (
        list(s3d_custom.get("badgeNamesZh") or [])[:4]
        if (s3d_custom and s3d_custom.get("badgeNamesZh"))
        else ["世界會員章", "旅條 · 區章", "小隊章", "專科章 ×12"]
    )
    toggles_raw = ui_raw.get("toggles") or fallback_toggles
    toggles = [_sanitize_text_for_font(str(x))[:14] for x in list(toggles_raw)[:4]]
    while len(toggles) < 4:
        toggles.append(["世界會員章", "旅條 · 區章", "小隊章", "專科章"][len(toggles)])

    ui_card = {
        "title": _sanitize_text_for_font(str(ui_raw.get("title") or "童軍動畫小劇場")),
        "toggles": toggles,
    }

    # 右下角超小「© SCOUT SYSTEM」水印（預設片中中間出現幾秒；可以 watermark.enabled=false 關掉）
    wm_raw = raw.get("watermark")
    if wm_raw is False:
        watermark = {"enabled": False, "text": "© SCOUT SYSTEM", "show_sec": 3.0, "position": "bottom-right"}
    elif isinstance(wm_raw, dict):
        watermark = {
            "enabled": bool(wm_raw.get("enabled", True)),
            "text": _sanitize_text_for_font(str(wm_raw.get("text") or "© SCOUT SYSTEM"))[:28],
            "show_sec": float(clamp(float(wm_raw.get("show_sec") or 3.0), 1.0, 12.0)),
            "position": "bottom-right",
        }
    else:
        watermark = {"enabled": True, "text": "© SCOUT SYSTEM", "show_sec": 3.0, "position": "bottom-right"}

    default_preset = str(raw.get("default_preset") or "story_arrival_meet")
    if default_preset not in PRESET_CATALOG:
        default_preset = "story_arrival_meet"

    shots_in = raw.get("shots") or []
    if not shots_in:
        raise ValueError("Episode spec must contain at least 1 shot in `shots`.")

    shots_norm: List[Dict[str, Any]] = []
    cur_frame = 0
    for idx, sh in enumerate(shots_in, start=1):
        preset = str(sh.get("preset") or default_preset)
        if preset not in PRESET_CATALOG:
            preset = default_preset
        dur = float(clamp(float(sh.get("duration") or 3.0), 1.2, 28.0))
        n_frames = max(12, int(round(dur * fps)))
        sh_char = resolve_character_preset(sh.get("char_preset"))
        sh_sec = _norm_story_section(sh.get("story_section") or sh.get("section"))
        if s3d_sec:
            # Pasted outfit code is authoritative for the hero actor.
            sec = str(sh.get("section") or s3d_sec or default_section)
        else:
            sec = str(sh_sec or default_section)
        if sec not in SECTION_STYLES:
            sec = default_section
        sh_skin = _norm_actor_skin(sh.get("actor_skin") or ep_actor_skin)
        gen = "F" if str(sh.get("gender") or sh_char.get("gender") or default_gender).upper() == "F" else "M"
        style_sh = str(sh.get("style_mode") or sh_char.get("style_mode") or hero_style)
        if style_sh not in ("bobo", "blocky", "morph"):
            style_sh = "morph" if preset == "scout3d_auto_snap" else hero_style
        # 每鏡一份角色陣容副本；鏡頭層級嘅 section / actor_skin / hat / show_sash 只覆蓋主角。
        cast_sh = [dict(c) for c in ep_cast]
        if sh_sec and sh_sec != cast_sh[0]["section"]:
            cast_sh[0]["section"] = sh_sec
            if "show_sash" not in sh:
                cast_sh[0]["show_sash"] = 1.0 if sh_sec == "scout" else 0.0
            if "hat" not in sh:
                cast_sh[0]["hat"] = None
        if "actor_skin" in sh:
            cast_sh[0]["skin"] = sh_skin
        cast_sh[0]["gender"] = gen
        cast_sh[0]["style_mode"] = style_sh
        if "hat" in sh:
            cast_sh[0]["hat"] = bool(sh["hat"])
        if "show_sash" in sh:
            cast_sh[0]["show_sash"] = float(sh["show_sash"] or 0.0)
        if sh.get("char_preset"):
            sh_char_ok = str(sh_char.get("section") or "") == cast_sh[0]["section"]
            if sh_char_ok:
                if "hat" not in sh and "hat" in sh_char:
                    cast_sh[0]["hat"] = bool(sh_char["hat"])
                if "show_sash" not in sh and "show_sash" in sh_char:
                    cast_sh[0]["show_sash"] = float(sh_char["show_sash"])
        if cast_sh[0]["section"] not in _ACTOR_SASH_SECTIONS:
            cast_sh[0]["show_sash"] = 0.0
        hat_sh = cast_sh[0]["hat"]
        sash_sh = cast_sh[0]["show_sash"]

        sub_txt = str(sh.get("subtitle") if sh.get("subtitle") is not None else (sh.get("narration") or ""))
        if subtitle_override and idx in subtitle_override:
            sub_txt = str(subtitle_override[idx])
        vo_raw = str(sh.get("narration") if sh.get("narration") is not None else sub_txt)

        sh_scene = _norm_scene(sh.get("scene") or sh.get("set"))
        if sh.get("scene_kind"):
            kind_override = _norm_scene_kind(sh.get("scene_kind"))
            if kind_override:
                base_scene = dict(sh_scene or ep_scene or {})
                sh_scene = {
                    **base_scene,
                    "kind": kind_override,
                    "props": base_scene.get("props") or list(_DEFAULT_SCENE_PROPS.get(kind_override, [])),
                    "framing": base_scene.get("framing", "medium"),
                    "float": base_scene.get("float", kind_override in ("space", "void", "sky")),
                    "palette": base_scene.get("palette", {}),
                }
        if sh_scene is None and ep_scene is not None:
            sh_scene = dict(ep_scene)

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
                "story_section": sec,
                "actor_skin": sh_skin,
                "gender": gen,
                "style_mode": style_sh,
                "hat": hat_sh,
                "show_sash": sash_sh,
                "camera": _norm_camera(sh.get("camera") if "camera" in sh else default_camera),
                "scene": sh_scene,
                "cast": cast_sh,
                "show_ui_card": bool(sh.get("show_ui_card", preset in ("scout3d_auto_snap", "disaster_wrong_badges"))),
                "trio_sections": trio_clean,
                "subtitle": _sanitize_text_for_font(sub_txt),
                "narration": _clean_cantonese_tts_text(vo_raw),
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
        "story_section": default_section,
        "actor_skin": ep_actor_skin,
        "gender": default_gender,
        "hero_style": hero_style,
        "characters": ep_cast,
        "camera": default_camera,
        "scene": ep_scene,
        "s3d_custom": s3d_custom,
        "bgm_mood": bgm_mood,
        "voice": voice,
        "voice_rate": voice_rate,
        "voice_engine": voice_engine,
        "voice_model": voice_model,
        "tts_command": tts_command,
        "ui_card": ui_card,
        "watermark": watermark,
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


def _apply_camera_move(cam: Camera3D, move: Any, u: float, lt: float) -> Camera3D:
    """Layer a user/AI camera move on top of a preset's native camera.

    `auto` keeps the preset's own camera. Every other move is a relative offset that
    ramps in with the shot timeline, so the first frame always matches the preset framing.
    """
    key = _norm_camera(move)
    if key == "auto":
        return cam

    k = smoothstep(clamp(float(u), 0.0, 1.0))
    rel = cam.target - cam.pos
    dist = float(np.linalg.norm(rel))
    if dist < 1e-5:
        return cam
    fwd = rel / dist
    right = np.cross(fwd, v3(0.0, 1.0, 0.0))
    rn = float(np.linalg.norm(right))
    right = v3(0.0, 0.0, 0.0) + (right / rn if rn > 1e-5 else v3(1.0, 0.0, 0.0))
    up = np.cross(right, fwd)
    up = up / max(1e-5, float(np.linalg.norm(up)))

    pos = cam.pos.copy()
    target = cam.target.copy()
    roll = float(cam.roll_deg)

    if key == "push_in":
        pos = pos + fwd * (0.62 * k)
    elif key == "pull_out":
        pos = pos - fwd * (0.78 * k)
    elif key in ("pan_left", "pan_right"):
        sign = -1.0 if key == "pan_left" else 1.0
        off = right * (0.55 * sign * k)
        pos = pos + off
        target = target + off * 0.92
    elif key == "tilt_up":
        pos = pos + up * (0.28 * k)
        target = target + up * (0.80 * k)
    elif key in ("orbit_left", "orbit_right"):
        sign = -1.0 if key == "orbit_left" else 1.0
        ang = math.radians(14.0 * sign * k)
        ca, sa = math.cos(ang), math.sin(ang)
        rx, rz = float(pos[0] - target[0]), float(pos[2] - target[2])
        pos = v3(float(target[0]) + rx * ca - rz * sa, float(pos[1]), float(target[2]) + rx * sa + rz * ca)
    elif key == "crane_up":
        pos = pos + v3(0.0, 0.78 * k, 0.0) - fwd * (0.28 * k)
        target = target + v3(0.0, 0.10 * k, 0.0)
    elif key == "low_angle":
        pos = pos + v3(0.0, -0.58, 0.0) + fwd * 0.18
        target = target + v3(0.0, 0.22, 0.0)
    elif key == "handheld":
        pos = pos + v3(math.sin(lt * 7.1) * 0.030, math.sin(lt * 8.7 + 1.3) * 0.022, 0.0)
        roll += math.sin(lt * 5.3) * 0.6

    return Camera3D(pos=pos, target=target, fov_deg=float(cam.fov_deg), roll_deg=roll)


_ACTOR_SASH_SECTIONS = ("scout", "sea_scout", "air_scout")


def _make_actor(
    section: str = "scout",
    skin: str = "human",
    gender: str = "M",
    hat: Optional[bool] = None,
    show_sash: Optional[float] = None,
    style_mode: str = "bobo",
    s3d_custom: Optional[Dict[str, Any]] = None,
    name: str = "",
) -> Dict[str, Any]:
    """Build a normalized cast member dict used by the story scene renderer."""
    sec = section if section in SECTION_STYLES else "scout"
    if show_sash is None:
        sash = 1.0 if sec == "scout" else 0.0
    else:
        sash = float(max(0.0, min(1.0, float(show_sash))))
    return {
        "name": name,
        "section": sec,
        "skin": _norm_actor_skin(skin),
        "gender": "F" if str(gender).upper().startswith(("F", "G")) else "M",
        "hat": hat,
        "show_sash": sash if sec in _ACTOR_SASH_SECTIONS else 0.0,
        "style_mode": style_mode if style_mode in ("bobo", "blocky", "morph") else "bobo",
        "s3d_custom": s3d_custom,
    }


def _slot_actor(sh: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Pick the character for a scene slot (hero / buddy / third / leader)."""
    cast: List[Dict[str, Any]] = list(sh.get("cast") or [])
    if cast:
        hero = cast[0]
    else:
        hero = _make_actor(
            str(sh.get("section") or "scout"),
            str(sh.get("actor_skin") or "human"),
            str(sh.get("gender") or "M"),
            sh.get("hat"),
            sh.get("show_sash"),
            str(sh.get("style_mode") or "bobo"),
        )
    if kind == "hero":
        return hero

    non_leaders = [c for c in cast[1:] if str(c.get("section")) != "leader"]
    if kind == "buddy" and non_leaders:
        return non_leaders[0]
    if kind == "third" and len(non_leaders) > 1:
        return non_leaders[1]
    if kind == "leader":
        leaders = [c for c in cast if str(c.get("section")) == "leader"]
        if leaders:
            return leaders[0]

    mate_sec = "scout" if hero.get("section") == "leader" else str(hero.get("section") or "scout")
    if kind == "buddy":
        return _make_actor(
            mate_sec, "human", "F" if hero.get("gender") == "M" else "M",
            hero.get("hat"), 0.0, "bobo",
        )
    if kind == "third":
        return _make_actor(mate_sec, "human", str(hero.get("gender") or "M"), hero.get("hat"), 0.0, "bobo")
    return _make_actor("leader", "human", "M", True, 0.0, "bobo")


def _draw_actor(
    sc: Scene3D,
    actor: Dict[str, Any],
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    style_mode: Optional[str] = None,
    expression: str = "happy",
    salute: float = 0.0,
    wave: float = 0.0,
    t_sec: float = 0.0,
) -> None:
    draw_scout_figure(
        sc, base_pos, yaw_deg=yaw_deg, scale=scale,
        style_mode=str(style_mode or actor.get("style_mode") or "bobo"),
        expression=expression,
        salute=salute, wave=wave, badge_mode="correct",
        show_sash=float(actor.get("show_sash") or 0.0),
        section=str(actor.get("section") or "scout"),
        gender=str(actor.get("gender") or "M"),
        hat=actor.get("hat"),
        t_sec=t_sec,
        s3d_custom=actor.get("s3d_custom"),
        actor_skin=str(actor.get("skin") or "human"),
    )


def _draw_slot(
    sc: Scene3D,
    sh: Dict[str, Any],
    kind: str,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    style_mode: Optional[str] = None,
    expression: str = "happy",
    salute: float = 0.0,
    wave: float = 0.0,
    t_sec: float = 0.0,
) -> Dict[str, Any]:
    actor = _slot_actor(sh, kind)
    _draw_actor(
        sc, actor, base_pos, yaw_deg=yaw_deg, scale=scale, style_mode=style_mode,
        expression=expression, salute=salute, wave=wave, t_sec=t_sec,
    )
    return actor


def _draw_remaining_cast(
    sc: Scene3D,
    sh: Dict[str, Any],
    used: Sequence[Dict[str, Any]],
    t_sec: float,
    back_z: float = -1.55,
) -> None:
    """Draw cast members that the preset's main slots did not use (up to 3) as a back row."""
    rest = [c for c in (sh.get("cast") or []) if not any(c is a for a in used)]
    slots = ((-1.15, -0.95, 12.0), (1.15, -0.95, -12.0), (0.0, back_z, 0.0))
    scales = (0.70, 0.70, 0.66)
    for i, actor in enumerate(rest[:3]):
        x, z, yaw = slots[i]
        _draw_actor(
            sc, actor, v3(x, 0.0, z), yaw_deg=yaw, scale=scales[i],
            expression="happy", wave=0.0, t_sec=t_sec + 0.25 * i,
        )


# ═══════════════════════════════════════════════════════════════════
# AI 自由場景：用幾何積木砌出太空、海底、城市、雪地、室內……
# ═══════════════════════════════════════════════════════════════════

_PROP_LAYOUT: Dict[str, Tuple[float, float, float, float]] = {
    "rocket":     (1.25, 0.00, -2.35, 0.95),
    "satellite":  (1.55, 2.55, -4.20, 1.00),
    "planet":     (-2.20, 2.90, -5.00, 0.95),
    "moon":       (2.05, 3.30, -4.90, 1.00),
    "cloud":      (-1.90, 3.10, -4.40, 1.00),
    "tent":       (-1.45, 0.00, -1.25, 0.95),
    "campfire":   (0.00, 0.00, -0.85, 1.00),
    "pine":       (-1.80, 0.00, -1.95, 1.35),
    "palm":       (1.25, 0.00, -1.70, 0.85),
    "rock":       (-1.35, 0.00, -0.90, 1.00),
    "crystal":    (1.20, 0.00, -0.85, 1.00),
    "snowman":    (1.20, 0.00, -0.90, 0.95),
    "balloon":    (1.35, 1.60, -1.40, 1.00),
    "building":   (1.70, 0.00, -3.60, 1.00),
    "streetlamp": (1.40, 0.00, -1.10, 1.00),
    "book":       (-1.05, 0.00, 0.35, 0.80),
    "flag":       (1.20, 0.00, -0.70, 1.00),
    "asteroid":   (-2.10, 1.40, -3.40, 1.00),
}


def _draw_stars(sc: Scene3D, t_sec: float, count: int = 46) -> None:
    rng = random.Random(7)
    for i in range(count):
        x = rng.uniform(-6.5, 6.5)
        y = rng.uniform(0.7, 6.9)
        z = rng.uniform(-7.0, -3.0)
        base = rng.uniform(0.30, 0.88)
        r = rng.uniform(0.016, 0.045)
        tw = base * (0.72 + 0.28 * math.sin(t_sec * 2.1 + i * 1.7))
        sc.add_sphere(v3(x, y, z), r, (1.0, 1.0, 0.94), emissive=(tw, tw, tw * 0.88))


def _draw_moon(sc: Scene3D, pos: np.ndarray, scale: float = 1.0) -> None:
    sc.add_sphere(pos, 0.56 * scale, hex_rgb01("#FFF6D8"), roughness=0.45, emissive=(0.30, 0.29, 0.22))
    sc.add_sphere(pos + v3(-0.18 * scale, 0.12 * scale, 0.46 * scale), 0.12 * scale, hex_rgb01("#E8DDBB"), roughness=0.7)


def _draw_planet(sc: Scene3D, pos: np.ndarray, scale: float = 1.0) -> None:
    radius = 1.15 * scale
    sc.add_sphere(pos, radius, hex_rgb01("#D9885C"), roughness=0.62)
    sc.add_sphere(pos + v3(0.35 * scale, 0.30 * scale, 0.72 * scale), 0.55 * scale, hex_rgb01("#C4714A"), roughness=0.65)
    rot = rot_x(math.radians(16.0)) @ rot_z(math.radians(-13.0))
    ring_r = radius * 1.55
    for i in range(26):
        ang = i * (2.0 * math.pi / 26.0)
        p = pos + rot @ v3(math.cos(ang) * ring_r, 0.0, math.sin(ang) * ring_r)
        sc.add_ellipsoid(p, v3(0.20 * scale, 0.032 * scale, 0.085 * scale), hex_rgb01("#F0C98C"), rot=rot, roughness=0.55)


def _draw_rocket(sc: Scene3D, base: np.ndarray, scale: float = 1.0, t_sec: float = 0.0) -> None:
    k = scale
    body_bot = base + v3(0.0, 0.55 * k, 0.0)
    body_top = base + v3(0.0, 2.42 * k, 0.0)
    sc.add_cylinder(body_bot, body_top, 0.33 * k, hex_rgb01("#F2F3F8"), roughness=0.34)
    sc.add_ellipsoid(base + v3(0.0, 2.42 * k, 0.0), v3(0.33 * k, 0.50 * k, 0.33 * k), hex_rgb01("#E2493F"), roughness=0.42)
    sc.add_sphere(base + v3(0.0, 1.62 * k, 0.28 * k), 0.15 * k, hex_rgb01("#9AD8FF"), roughness=0.12, emissive=(0.30, 0.55, 0.80))
    for sx in (-1.0, 1.0):
        sc.add_rounded_box(
            base + v3(sx * 0.38 * k, 0.86 * k, 0.0),
            v3(0.20 * k, 0.33 * k, 0.055 * k), 0.045 * k,
            hex_rgb01("#E2493F"), rot=rot_y(math.radians(sx * 8.0)),
        )
    flame = 0.58 + 0.20 * math.sin(t_sec * 19.0)
    sc.add_ellipsoid(
        base + v3(0.0, 0.55 * k - 0.34 * k, 0.0),
        v3(0.19 * k, 0.42 * k * flame, 0.19 * k),
        hex_rgb01("#FFB13C"), roughness=0.2, emissive=(1.0, 0.55, 0.12),
    )


def _draw_satellite(sc: Scene3D, pos: np.ndarray, scale: float = 1.0, t_sec: float = 0.0) -> None:
    k = scale
    sc.add_rounded_box(pos, v3(0.26 * k, 0.16 * k, 0.16 * k), 0.05 * k, hex_rgb01("#D9DEE8"), rot=rot_y(math.radians(18.0)))
    for sx in (-1.0, 1.0):
        sc.add_rounded_box(pos + v3(sx * 0.62 * k, 0.0, 0.0), v3(0.33 * k, 0.015 * k, 0.20 * k), 0.012 * k,
                           hex_rgb01("#2C5AA0"), rot=rot_y(math.radians(18.0)), roughness=0.3)
    sc.add_sphere(pos + v3(0.0, 0.22 * k, 0.0), 0.055 * k, hex_rgb01("#FFD66B"), emissive=(0.9, 0.7, 0.2))
    blink = 0.5 + 0.5 * math.sin(t_sec * 3.0)
    sc.add_sphere(pos + v3(0.0, -0.24 * k, 0.0), 0.05 * k, hex_rgb01("#FF6B6B"), emissive=(blink, 0.1, 0.1))


def _draw_cloud(sc: Scene3D, pos: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    for dx, dy, r in ((-0.42, 0.0, 0.34), (0.0, 0.14, 0.46), (0.44, -0.02, 0.32), (0.12, -0.14, 0.30)):
        sc.add_sphere(pos + v3(dx * k, dy * k, 0.0), r * k, hex_rgb01("#F7FBFF"), roughness=0.95)


def _draw_palm(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    trunk_col = hex_rgb01("#8A5A32")
    p0 = base
    p1 = base + v3(0.12 * k, 1.10 * k, 0.0)
    p2 = base + v3(0.20 * k, 2.10 * k, 0.0)
    sc.add_cylinder(p0, p1, 0.085 * k, trunk_col, roughness=0.8)
    sc.add_cylinder(p1, p2, 0.075 * k, trunk_col, roughness=0.8)
    top = p2
    leaf_col = hex_rgb01("#2E9E5B")
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0) + 0.3
        tip = top + v3(math.cos(ang) * 0.95 * k, 0.30 * k + 0.18 * math.sin(i * 1.4), math.sin(ang) * 0.95 * k)
        mid = 0.5 * (top + tip)
        d = tip - top
        yaw = math.degrees(math.atan2(float(d[0]), float(d[2])))
        sc.add_ellipsoid(mid, v3(0.16 * k, 0.075 * k, 0.62 * k), leaf_col, rot=rot_y(math.radians(yaw)), roughness=0.8)
    for dx in (-0.10, 0.08):
        sc.add_sphere(top + v3(dx * k, -0.12 * k, 0.10 * k), 0.085 * k, hex_rgb01("#6B4A2A"), roughness=0.7)


def _draw_rock(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    col = hex_rgb01("#7C8088")
    sc.add_ellipsoid(base + v3(0.0, 0.24 * k, 0.0), v3(0.42 * k, 0.30 * k, 0.36 * k), col, roughness=0.9)
    sc.add_ellipsoid(base + v3(0.34 * k, 0.15 * k, 0.12 * k), v3(0.24 * k, 0.20 * k, 0.20 * k), col, roughness=0.9)
    sc.add_ellipsoid(base + v3(-0.30 * k, 0.12 * k, 0.16 * k), v3(0.18 * k, 0.15 * k, 0.17 * k), col, roughness=0.9)


def _draw_crystal(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    col = hex_rgb01("#8FE8FF")
    for dx, dz, h, tilt in ((-0.18, 0.0, 0.85, -8.0), (0.10, 0.08, 1.15, 5.0), (0.26, -0.10, 0.62, 12.0)):
        sc.add_ellipsoid(
            base + v3(dx * k, h * 0.5 * k, dz * k),
            v3(0.14 * k, h * 0.5 * k, 0.14 * k),
            col, rot=rot_z(math.radians(tilt)), roughness=0.18,
            emissive=(0.28, 0.55, 0.65),
        )


def _draw_snowman(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    white = hex_rgb01("#F7FBFF")
    sc.add_sphere(base + v3(0.0, 0.38 * k, 0.0), 0.40 * k, white, roughness=0.85)
    sc.add_sphere(base + v3(0.0, 0.98 * k, 0.0), 0.28 * k, white, roughness=0.85)
    sc.add_sphere(base + v3(0.0, 1.38 * k, 0.0), 0.20 * k, white, roughness=0.85)
    sc.add_sphere(base + v3(0.0, 1.58 * k, 0.0), 0.12 * k, white, roughness=0.85)
    sc.add_sphere(base + v3(0.0, 1.40 * k, 0.19 * k), 0.05 * k, hex_rgb01("#E8802F"), roughness=0.6)
    for dx in (-0.07, 0.07):
        sc.add_sphere(base + v3(dx * k, 1.46 * k, 0.16 * k), 0.025 * k, hex_rgb01("#22252A"), roughness=0.4)


def _draw_balloon(sc: Scene3D, pos: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    sc.add_ellipsoid(pos, v3(0.30 * k, 0.36 * k, 0.30 * k), hex_rgb01("#F26B7A"), roughness=0.28)
    sc.add_cylinder(pos + v3(0.0, -0.35 * k, 0.0), pos + v3(0.0, -1.15 * k, 0.0), 0.01 * k, hex_rgb01("#DDDDE3"))


def _draw_building(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    for i in range(3):
        bx = base[0] + i * 0.92 * k
        h = (2.1 + 0.55 * (i % 2)) * k
        z = base[2] - 0.30 * i * k
        sc.add_rounded_box(v3(bx, h * 0.5, z), v3(0.42 * k, h * 0.5, 0.40 * k), 0.03 * k,
                           hex_rgb01("#3B3F52"), roughness=0.7)
        for row in range(3):
            for col in range(2):
                lit = 0.5 + 0.5 * math.sin(row * 2.1 + col * 1.7 + i)
                sc.add_sphere(
                    v3(bx + (-0.16 + 0.32 * col) * k, (0.55 + row * 0.55) * k, z + 0.43 * k),
                    0.06 * k, hex_rgb01("#FFD27A"), roughness=0.2,
                    emissive=(0.75 * lit, 0.58 * lit, 0.18 * lit),
                )


def _draw_streetlamp(sc: Scene3D, base: np.ndarray, scale: float = 1.0) -> None:
    k = scale
    sc.add_cylinder(base, base + v3(0.0, 2.45 * k, 0.0), 0.045 * k, hex_rgb01("#2F3440"))
    sc.add_sphere(base + v3(0.0, 2.52 * k, 0.0), 0.16 * k, hex_rgb01("#FFE7A6"), roughness=0.2, emissive=(0.85, 0.72, 0.35))


def _draw_flag(sc: Scene3D, base: np.ndarray, scale: float = 1.0, t_sec: float = 0.0) -> None:
    k = scale
    sc.add_cylinder(base, base + v3(0.0, 2.15 * k, 0.0), 0.035 * k, hex_rgb01("#C9CCD4"))
    wave = 0.10 * math.sin(t_sec * 4.2)
    sc.add_rounded_box(base + v3(0.36 * k, 1.80 * k, wave * k), v3(0.34 * k, 0.22 * k, 0.02 * k), 0.015 * k,
                       hex_rgb01("#E04A57"), rot=rot_y(math.radians(wave * 24.0)))


def _draw_weather(sc: Scene3D, kind: str, t_sec: float) -> None:
    if kind == "snow":
        for i in range(34):
            seed = i * 0.618
            y = 4.2 - ((t_sec * 0.45 + seed * 3.1) % 4.6)
            x = -5.0 + (seed * 10.0) % 10.0
            z = -3.4 - (seed * 4.3) % 2.6
            sc.add_sphere(v3(x, y, z), 0.028, hex_rgb01("#FFFFFF"), emissive=(0.35, 0.38, 0.42))
    elif kind == "underwater":
        for i in range(22):
            seed = i * 0.731
            y = 0.2 + ((t_sec * 0.32 + seed * 3.7) % 4.2)
            x = -3.6 + (seed * 7.0) % 7.2
            z = -2.2 - (seed * 2.2) % 1.6
            sc.add_sphere(v3(x, y, z), 0.035 + 0.02 * ((i % 3) / 2.0), hex_rgb01("#BFF7FF"), roughness=0.1, emissive=(0.25, 0.45, 0.48))


def _draw_clouds_backdrop(sc: Scene3D, t_sec: float) -> None:
    for i, (x, y, z, s) in enumerate(((-2.4, 3.2, -4.8, 1.1), (1.9, 3.8, -5.2, 0.9), (0.2, 2.7, -5.6, 0.75))):
        _draw_cloud(sc, v3(x + 0.15 * math.sin(t_sec * 0.4 + i), y, z), s)


def _draw_scene_props(sc: Scene3D, scene: Dict[str, Any], t_sec: float) -> None:
    kind = str(scene.get("kind") or "sky")
    framing = str(scene.get("framing") or "medium")
    # 特寫鏡以角色表情為主：大型側邊道具會變成半截雜物，直接略過。
    skip_closeup = {"rocket", "building", "tent", "palm", "satellite", "streetlamp", "snowman", "flag"}
    counts: Dict[str, int] = {}
    for name in (scene.get("props") or []):
        if framing == "closeup" and name in skip_closeup:
            continue
        n = counts.get(name, 0)
        counts[name] = n + 1
        if name == "stars":
            _draw_stars(sc, t_sec)
        elif name == "bubble":
            _draw_weather(sc, "underwater", t_sec)
        elif name == "cloud":
            _draw_cloud(sc, v3(-1.9 + n * 1.7, 3.1 + 0.25 * (n % 2), -4.4), 1.0)
        elif name == "moon":
            _draw_moon(sc, v3(2.50, 3.40, -5.00), 1.0)
        elif name == "planet":
            _draw_planet(sc, v3(-2.70, 2.95, -5.20), 1.0)
        elif name == "rocket":
            _draw_rocket(sc, v3(1.25 + n * 0.7, 0.10, -2.35), 0.95, t_sec)
        elif name == "satellite":
            _draw_satellite(sc, v3(1.70, 2.55, -4.20), 1.0, t_sec)
        elif name == "building":
            _draw_building(sc, v3(1.60 + n * 0.5, 0.0, -3.60), 1.0)
        elif name == "streetlamp":
            _draw_streetlamp(sc, v3(1.40 + n * 0.55, 0.0, -1.10), 1.0)
        elif name == "tent":
            draw_camp_tent(sc, v3(-1.45 - n * 0.55, 0.0, -1.25), yaw_deg=20.0, scale=0.95)
        elif name == "campfire":
            draw_campfire(sc, v3(0.0, 0.0, -0.85), scale=1.0, t_sec=t_sec)
        elif name == "pine":
            draw_pine_tree(sc, v3(-1.80 - n * 0.5, 0.0, -1.95), scale=1.35)
        elif name == "palm":
            _draw_palm(sc, v3(1.25 + n * 0.6, 0.0, -1.70), 0.85)
        elif name == "rock":
            _draw_rock(sc, v3(-1.45 + n * 0.55, 0.0, -0.90), 1.0)
        elif name == "asteroid":
            _draw_rock(sc, v3(-2.10 + n * 0.6, 1.40, -3.40), 1.25)
        elif name == "crystal":
            _draw_crystal(sc, v3(1.20 + n * 0.55, 0.0, -0.85), 1.0)
        elif name == "snowman":
            _draw_snowman(sc, v3(1.20 + n * 0.6, 0.0, -0.90), 0.95)
        elif name == "balloon":
            _draw_balloon(sc, v3(1.55 + n * 0.4, 1.60, -1.40), 1.0)
        elif name == "book":
            draw_handbook_stack(sc, v3(-1.05, 0.0, 0.35), yaw_deg=-12.0, scale=0.8)
        elif name == "flag":
            _draw_flag(sc, v3(1.20 + n * 0.4, 0.0, -0.70), 1.0, t_sec)
    if kind == "sky":
        _draw_clouds_backdrop(sc, t_sec)
    elif kind == "beach":
        sc.add_ellipsoid(v3(0.0, 0.06, -3.30), v3(6.2, 0.05, 2.3), hex_rgb01("#3E9FD8"), roughness=0.15)
        for i in range(4):
            sc.add_ellipsoid(v3(-2.4 + i * 1.6, 0.10, -2.35), v3(0.85, 0.035, 0.16), hex_rgb01("#BFEFFF"), roughness=0.2)


_CUSTOM_CAST_LAYOUT: Dict[int, Tuple[Tuple[float, float, float, float], ...]] = {
    1: ((0.00, 0.42, 0.0, 0.94),),
    2: ((-0.42, 0.38, 10.0, 0.94), (0.60, 0.18, -16.0, 0.88)),
    3: ((0.00, 0.55, 0.0, 0.94), (-0.95, 0.02, 20.0, 0.88), (0.98, 0.00, -20.0, 0.88)),
    4: ((-0.38, 0.52, 8.0, 0.92), (0.52, 0.44, -8.0, 0.88), (-1.12, -0.22, 20.0, 0.84), (1.14, -0.24, -20.0, 0.84)),
    5: ((0.00, 0.62, 0.0, 0.94), (-0.62, 0.42, 10.0, 0.88), (0.64, 0.40, -10.0, 0.88),
        (-1.25, -0.36, 20.0, 0.82), (1.27, -0.38, -20.0, 0.82)),
}


def _draw_custom_cast(sc: Scene3D, sh: Dict[str, Any], u: float, lt: float, floaty: bool, framing: str) -> None:
    cast = list(sh.get("cast") or [])
    if not cast:
        cast = [_slot_actor(sh, "hero")]
    cast = cast[:5]
    if framing == "closeup":
        actor = cast[0]
        y = (0.12 if floaty else 0.0)
        _draw_actor(sc, actor, v3(0.0, y, 0.15), yaw_deg=lerp(-12.0, 12.0, smoothstep(u)),
                    scale=1.0, expression="happy", t_sec=lt)
        return
    layout = _CUSTOM_CAST_LAYOUT.get(len(cast), _CUSTOM_CAST_LAYOUT[1])
    for i, (actor, (x, z, yaw, scl)) in enumerate(zip(cast, layout)):
        bob = 0.055 * math.sin(lt * 1.35 + i * 0.9) if floaty else 0.0
        y = (0.12 if floaty else 0.0) + bob
        sway = 2.5 * math.sin(lt * 1.2 + i * 1.1)
        _draw_actor(sc, actor, v3(x, y, z), yaw_deg=yaw + sway, scale=scl,
                    expression="proud" if i == 2 and len(cast) >= 3 else "happy",
                    t_sec=lt + i * 0.15)


def _bp_rot_matrix(rot: Tuple[float, float, float]) -> np.ndarray:
    return rot_y(float(rot[1])) @ rot_x(float(rot[0])) @ rot_z(float(rot[2]))


def _bp_color_pair(color: str, glow: float) -> Tuple[Any, Optional[Any]]:
    rgb = hex_rgb01(color)
    if glow <= 0.001:
        return rgb, None
    return rgb, tuple(float(c) * glow for c in rgb)


def _bp_pose(obj: Dict[str, Any], t_sec: float, seed: float) -> Tuple[float, float, float, float, float]:
    anim = obj.get("anim")
    if not anim or anim.get("kind") == "none":
        return 0.0, 0.0, 0.0, 1.0, 0.0
    amp = float(anim.get("amp", 0.12))
    speed = float(anim.get("speed", 1.0))
    phase = float(anim.get("phase", 0.0)) + seed * 0.37
    kind = anim.get("kind")
    if kind == "bob":
        return 0.0, amp * math.sin(speed * t_sec + phase), 0.0, 1.0, 0.0
    if kind == "drift":
        return (amp * math.sin(speed * t_sec + phase),
                amp * 0.35 * math.sin(speed * 0.7 * t_sec + phase * 1.3),
                amp * 0.6 * math.cos(speed * 0.8 * t_sec + phase),
                1.0, 0.0)
    if kind == "spin":
        return 0.0, 0.0, 0.0, 1.0, speed * 45.0 * t_sec
    if kind == "pulse":
        return 0.0, 0.0, 0.0, max(0.2, 1.0 + amp * math.sin(speed * 2.0 * t_sec + phase)), 0.0
    return 0.0, 0.0, 0.0, 1.0, 0.0


def _bp_draw_copy(
    sc: Scene3D,
    obj: Dict[str, Any],
    center: Tuple[float, float, float],
    scale: float,
    extra_rot: float,
    t_sec: float,
    floor_y: Optional[float],
) -> None:
    shape = obj["shape"]
    size = obj["size"]
    rot = obj["rot"]
    rgb, em = _bp_color_pair(obj["color"], float(obj.get("glow") or 0.0))
    rough = float(obj.get("rough") or 0.5)
    scale = max(0.05, scale)
    cx, cy, cz = center

    if shape == "sphere":
        radius = max(0.01, size[0] * scale)
        sc.add_sphere(v3(cx, cy, cz), radius, rgb, roughness=rough, emissive=em)
        bound = radius
    elif shape == "ellipsoid":
        radii = (max(0.01, size[0] * scale), max(0.01, size[1] * scale), max(0.01, size[2] * scale))
        mat = _bp_rot_matrix((rot[0], rot[1] + extra_rot, rot[2]))
        sc.add_ellipsoid(v3(cx, cy, cz), v3(*radii), rgb, rot=mat, roughness=rough, emissive=em)
        bound = max(radii)
    elif shape == "box":
        half = (max(0.01, size[0] * scale), max(0.01, size[1] * scale), max(0.01, size[2] * scale))
        mat = _bp_rot_matrix((rot[0], rot[1] + extra_rot, rot[2]))
        bevel = max(0.0, min(min(half) * 0.9, float(obj.get("bevel") or 0.0) * scale))
        sc.add_rounded_box(v3(cx, cy, cz), v3(*half), bevel, rgb, rot=mat, roughness=rough, emissive=em)
        bound = max(half)
    elif shape in ("capsule", "cylinder"):
        radius = max(0.01, size[0] * scale)
        half_len = max(0.01, size[1] * 0.5 * scale)
        axis = str(obj.get("axis") or "y").lower()[:1]
        off = {"x": (half_len, 0.0, 0.0), "z": (0.0, 0.0, half_len)}.get(axis, (0.0, half_len, 0.0))
        pa = v3(cx - off[0], cy - off[1], cz - off[2])
        pb = v3(cx + off[0], cy + off[1], cz + off[2])
        if shape == "capsule":
            sc.add_capsule(pa, pb, radius, rgb, roughness=rough, emissive=em)
        else:
            sc.add_cylinder(pa, pb, radius, rgb, roughness=rough, emissive=em)
        bound = math.hypot(half_len, radius)
    elif shape == "ring":
        radius = max(0.05, size[0] * scale)
        tube = max(0.008, float(obj.get("tube") or 0.08) * scale)
        count = int(obj.get("count") or 48)
        mat = _bp_rot_matrix((rot[0], rot[1] + extra_rot, rot[2]))
        for i in range(count):
            ang = 2.0 * math.pi * i / count
            base = np.array([math.cos(ang) * radius, 0.0, math.sin(ang) * radius], dtype=np.float32)
            p = mat @ base
            sc.add_sphere(v3(cx + float(p[0]), cy + float(p[1]), cz + float(p[2])), tube, rgb, roughness=rough, emissive=em)
        bound = radius + tube
    else:
        return

    if floor_y is not None and cy - bound <= floor_y + 0.06:
        sc.add_floor_shadow(cx, cz, max(0.08, bound * 1.05), 0.16)


def _draw_blueprint(sc: Scene3D, scene: Dict[str, Any], t_sec: float, floor_y: Optional[float]) -> None:
    for i, obj in enumerate(scene.get("objects") or []):
        repeat = obj.get("repeat")
        seed = float(obj.get("seed") or 0.0) + i * 7.31
        dx, dy, dz, pulse_scale, extra_rot = _bp_pose(obj, t_sec, seed)
        if not repeat:
            _bp_draw_copy(sc, obj, (obj["pos"][0] + dx, obj["pos"][1] + dy, obj["pos"][2] + dz),
                          pulse_scale, extra_rot, t_sec, floor_y)
            continue
        rng = random.Random(int(repeat["seed"]) + i * 977)
        area = repeat["area"]
        for _ in range(int(repeat["count"])):
            px = rng.uniform(area[0][0], area[0][1]) + dx
            py = rng.uniform(area[1][0], area[1][1]) + dy
            pz = rng.uniform(area[2][0], area[2][1]) + dz
            jitter = rng.uniform(0.7, 1.35)
            _bp_draw_copy(sc, obj, (px, py, pz), pulse_scale * jitter, extra_rot, t_sec, floor_y)



def _render_custom_scene(spec: Dict[str, Any], sh: Dict[str, Any], frame_idx: int) -> Image.Image:
    W_px: int = spec["width"]
    H_px: int = spec["height"]
    fps: int = spec["fps"]
    aspect: str = spec["aspect"]
    fov_s, z_s = _cam_framing_scale(aspect)

    scene = sh.get("scene") or {}
    kind = str(scene.get("kind") or "")
    objects = scene.get("objects") or []
    style = _SCENE_STYLES.get(kind)
    if style is None:
        style = {
            "bg_top": "#0B1224" if objects else "#63ACE6",
            "bg_bot": "#1B2440" if objects else "#EAF7FF",
            "floor": None,
            "key": (-0.40, 0.72, 0.60),
            "rim": "#9CC4FF",
        }
    palette = scene.get("palette") or {}
    light = scene.get("light") or {}

    local_f = frame_idx - sh["start_frame"]
    u = local_f / float(max(1, sh["num_frames"] - 1))
    lt = local_f / float(fps)
    e = smoothstep(u)

    framing = str(scene.get("framing") or "medium")
    if framing not in ("wide", "medium", "closeup"):
        framing = "medium"
    if framing == "closeup":
        base_z, fov_deg, cam_y, target_y = 3.05, 33.0, 1.82, 1.72
    elif framing == "wide":
        base_z, fov_deg, cam_y, target_y = 8.70, 38.5, 1.98, 1.36
    else:
        base_z, fov_deg, cam_y, target_y = 7.15, 37.5, 1.92, 1.36

    cam = Camera3D(
        pos=v3(math.sin(lt * 0.55) * 0.06, cam_y, base_z * z_s),
        target=v3(0.0, target_y, 0.0),
        fov_deg=fov_deg * fov_s,
    )
    cam = _apply_camera_move(cam, sh.get("camera"), u, lt)

    floor_spec = scene.get("floor")
    if floor_spec is False:
        floor_hex = None
    elif isinstance(floor_spec, str) and floor_spec:
        floor_hex = floor_spec
    else:
        floor_hex = palette.get("floor") or style.get("floor")
    floor_y = None if not floor_hex else float(scene.get("floor_y") or 0.0)
    key_dir = light.get("dir") or style["key"]
    sc = Scene3D(
        W_px, H_px, cam,
        bg_top=hex_rgb01(palette.get("sky_top") or style["bg_top"]),
        bg_bot=hex_rgb01(palette.get("sky_bottom") or style["bg_bot"]),
        floor_y=floor_y,
        floor_color=hex_rgb01(floor_hex or style["bg_bot"]),
        key_dir=key_dir,
        rim_color=hex_rgb01(light.get("rim") or style["rim"]),
    )

    if kind in ("space", "night", "void"):
        _draw_stars(sc, lt, 40 if kind == "space" else 30)
    if kind:
        _draw_weather(sc, kind, lt)
    _draw_blueprint(sc, scene, lt, floor_y)
    _draw_scene_props(sc, scene, lt)
    if scene.get("cast", True) is not False:
        _draw_custom_cast(sc, sh, u, lt, bool(scene.get("float")), framing)
    return sc.render()


def render_shot_3d_frame(spec: Dict[str, Any], frame_idx: int) -> Image.Image:
    """Render one clean 3D frame (zero baked text) for any preset & aspect ratio."""
    W_px: int = spec["width"]
    H_px: int = spec["height"]
    fps: int = spec["fps"]
    aspect: str = spec["aspect"]
    fov_s, z_s = _cam_framing_scale(aspect)

    sh = _find_shot(spec, frame_idx)
    if sh.get("scene"):
        return _render_custom_scene(spec, sh, frame_idx)
    preset = sh["preset"]
    sec = sh["section"]
    gen = sh["gender"]
    sh_hat = sh.get("hat")
    s3d_custom = spec.get("s3d_custom")
    hero_style = "blocky" if sh["style_mode"] == "blocky" else "bobo"
    if sh.get("show_sash") is not None:
        sec_has_sash = float(sh["show_sash"]) if sec in ("scout", "sea_scout", "air_scout") else 0.0
    else:
        sec_has_sash = 1.0 if sec == "scout" else 0.0

    t = frame_idx / float(fps)
    local_f = frame_idx - sh["start_frame"]
    u = local_f / float(max(1, sh["num_frames"] - 1))
    lt = local_f / float(fps)
    e = smoothstep(u)

    # =====================================================================
    # GENERAL SCOUT STORY SCENES (pure 3D storytelling — zero app promo / UI)
    # =====================================================================
    if preset.startswith("story_"):
        act = str(sh.get("actor_skin") or "human")

        if preset == "story_arrival_meet":
            wave_u = smoothstep(lt / 0.55)
            cam = Camera3D(
                pos=v3(lerp(-0.20, 0.06, e), lerp(1.98, 1.90, e), lerp(8.15, 7.15, e) * z_s),
                target=v3(0.0, 1.34, 0.0),
                fov_deg=38.0 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#8FD4F5"), bg_bot=hex_rgb01("#EAF9DE"),
                floor_y=0.0, floor_color=hex_rgb01("#A8D894"),
                key_dir=(-0.42, 0.78, 0.60), rim_color=hex_rgb01("#FFF7CC"),
            )
            draw_pine_tree(sc, v3(-1.72, 0.0, -1.55), scale=1.55)
            draw_pine_tree(sc, v3(1.66, 0.0, -1.85), scale=1.30)
            draw_camp_tent(sc, v3(-1.35, 0.0, -1.05), yaw_deg=24.0, scale=0.86)
            a1 = _draw_slot(sc, sh, "hero", v3(lerp(-0.86, -0.38, e), 0.0, 0.26),
                            yaw_deg=12.0, scale=0.88, style_mode=hero_style,
                            expression="happy", wave=wave_u, t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(0.52, 0.0, -0.10),
                            yaw_deg=-20.0, scale=0.86, expression="happy",
                            wave=1.0, t_sec=t + 0.7)
            _draw_remaining_cast(sc, sh, [a1, a2], t)
            return sc.render()

        if preset == "story_group_chat":
            cam = Camera3D(
                pos=v3(lerp(0.06, -0.06, e), lerp(1.92, 1.86, e), lerp(7.55, 6.95, e) * z_s),
                target=v3(0.0, 1.34, 0.0),
                fov_deg=37.5 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#9BD8F0"), bg_bot=hex_rgb01("#F1FBE6"),
                floor_y=0.0, floor_color=hex_rgb01("#B3DDA1"),
                key_dir=(-0.46, 0.76, 0.58), rim_color=hex_rgb01("#FFF8DA"),
            )
            draw_pine_tree(sc, v3(1.95, 0.0, -2.15), scale=1.45)
            draw_pine_tree(sc, v3(-1.92, 0.0, -2.05), scale=1.25)
            sway_a = math.sin(t * 1.9) * 4.0
            sway_b = math.sin(t * 1.6 + 1.7) * 4.0
            a1 = _draw_slot(sc, sh, "hero", v3(-0.72, 0.0, 0.34),
                            yaw_deg=26.0 + sway_a, scale=0.86, style_mode=hero_style,
                            expression="happy", t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(0.68, 0.0, 0.30),
                            yaw_deg=-26.0 + sway_b, scale=0.85, expression="happy",
                            t_sec=t + 0.5)
            a3 = _draw_slot(sc, sh, "third", v3(0.02, 0.0, -0.72),
                            yaw_deg=2.0, scale=0.80,
                            expression="proud" if act != "ai_robot" else "happy",
                            t_sec=t + 1.1)
            _draw_remaining_cast(sc, sh, [a1, a2, a3], t, back_z=-1.35)
            return sc.render()

        if preset == "story_leader_briefing":
            cam = Camera3D(
                pos=v3(lerp(-0.10, 0.08, e), lerp(1.96, 1.90, e), lerp(7.85, 7.05, e) * z_s),
                target=v3(0.0, 1.38, 0.0),
                fov_deg=37.5 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#8ECBEE"), bg_bot=hex_rgb01("#EDF9F1"),
                floor_y=0.0, floor_color=hex_rgb01("#CFE7D2"),
                key_dir=(-0.44, 0.77, 0.60), rim_color=hex_rgb01("#FFF6D2"),
            )
            draw_pine_tree(sc, v3(-1.85, 0.0, -1.95), scale=1.35)
            draw_camp_tent(sc, v3(1.62, 0.0, -1.35), yaw_deg=-22.0, scale=0.82)
            a1 = _draw_slot(sc, sh, "leader", v3(0.62, 0.0, 0.10),
                            yaw_deg=-24.0, scale=0.94, expression="happy",
                            wave=1.0, t_sec=t)
            a2 = _draw_slot(sc, sh, "hero", v3(-0.52, 0.0, 0.30),
                            yaw_deg=16.0, scale=0.86, style_mode=hero_style,
                            expression="happy", t_sec=t + 0.4)
            _draw_remaining_cast(sc, sh, [a1, a2], t, back_z=-1.40)
            return sc.render()

        if preset == "story_challenge_oops":
            shake_x = math.sin(t * 21.0) * 0.020 * smoothstep(lt / 0.45)
            cam = Camera3D(
                pos=v3(lerp(0.06, -0.04, e) + shake_x, lerp(1.98, 1.90, e), lerp(7.75, 7.00, e) * z_s),
                target=v3(0.0, 1.35, 0.0),
                fov_deg=37.5 * fov_s,
                roll_deg=math.sin(t * 8.0) * 0.7,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#A9A0C4"), bg_bot=hex_rgb01("#F2EAD8"),
                floor_y=0.0, floor_color=hex_rgb01("#C6BBA4"),
                key_dir=(-0.45, 0.76, 0.58), rim_color=hex_rgb01("#FFD9A8"),
            )
            draw_handbook_stack(sc, v3(-0.86, 0.0, 0.62), yaw_deg=22.0, scale=0.80)
            a1 = _draw_slot(sc, sh, "hero", v3(-0.20, 0.0, 0.24),
                            yaw_deg=math.sin(t * 5.0) * 8.0, scale=0.88,
                            style_mode=hero_style, expression="nervous", t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(0.70, 0.0, -0.14),
                            yaw_deg=-22.0, scale=0.86, expression="surprised",
                            wave=1.0, t_sec=t + 0.6)
            _draw_remaining_cast(sc, sh, [a1, a2], t)
            return sc.render()

        if preset == "story_camp_outdoors":
            cam = Camera3D(
                pos=v3(lerp(-0.12, 0.10, e), lerp(2.02, 1.94, e), lerp(8.35, 7.45, e) * z_s),
                target=v3(0.0, 1.36, 0.0),
                fov_deg=38.5 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#8CCFEF"), bg_bot=hex_rgb01("#E7F6D7"),
                floor_y=0.0, floor_color=hex_rgb01("#9FD18C"),
                key_dir=(-0.40, 0.79, 0.58), rim_color=hex_rgb01("#FFF6C8"),
            )
            draw_pine_tree(sc, v3(-1.94, 0.0, -2.20), scale=1.70)
            draw_pine_tree(sc, v3(1.78, 0.0, -2.05), scale=1.45)
            draw_pine_tree(sc, v3(0.15, 0.0, -2.75), scale=1.15)
            draw_camp_tent(sc, v3(-0.95, 0.0, -0.95), yaw_deg=18.0, scale=1.12)
            a1 = _draw_slot(sc, sh, "hero", v3(0.42, 0.0, 0.30),
                            yaw_deg=-8.0, scale=0.88, style_mode=hero_style,
                            expression="happy", wave=1.0, t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(1.10, 0.0, -0.42),
                            yaw_deg=-30.0, scale=0.82, expression="happy",
                            wave=1.0, t_sec=t + 0.6)
            _draw_remaining_cast(sc, sh, [a1, a2], t)
            return sc.render()

        if preset == "story_team_task":
            cam = Camera3D(
                pos=v3(lerp(0.08, -0.10, e), lerp(1.94, 1.88, e), lerp(7.35, 6.75, e) * z_s),
                target=v3(0.0, 1.16, 0.10),
                fov_deg=37.0 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#93D2EE"), bg_bot=hex_rgb01("#EFFAE2"),
                floor_y=0.0, floor_color=hex_rgb01("#AEDC9C"),
                key_dir=(-0.44, 0.77, 0.60), rim_color=hex_rgb01("#FFF7D0"),
            )
            draw_pine_tree(sc, v3(1.92, 0.0, -2.10), scale=1.30)
            draw_camp_tent(sc, v3(-1.55, 0.0, -1.60), yaw_deg=22.0, scale=0.82)
            draw_handbook_stack(sc, v3(0.02, 0.0, 0.30), yaw_deg=-12.0, scale=0.72)
            a1 = _draw_slot(sc, sh, "hero", v3(-0.62, 0.0, 0.06),
                            yaw_deg=22.0, scale=0.86, style_mode=hero_style,
                            expression="happy", t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(0.68, 0.0, 0.06),
                            yaw_deg=-22.0, scale=0.84, expression="happy",
                            t_sec=t + 0.5)
            _draw_remaining_cast(sc, sh, [a1, a2], t, back_z=-1.45)
            return sc.render()

        if preset == "story_campfire_night":
            cam = Camera3D(
                pos=v3(lerp(-0.06, 0.08, e), lerp(1.86, 1.80, e), lerp(7.15, 6.55, e) * z_s),
                target=v3(0.0, 1.22, 0.0),
                fov_deg=38.0 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#141B33"), bg_bot=hex_rgb01("#3A2C3E"),
                floor_y=0.0, floor_color=hex_rgb01("#2A2C33"),
                key_dir=(-0.36, 0.62, 0.70), rim_color=hex_rgb01("#FFB15C"),
            )
            draw_pine_tree(sc, v3(-2.05, 0.0, -2.35), scale=1.55)
            draw_pine_tree(sc, v3(2.00, 0.0, -2.30), scale=1.40)
            draw_campfire(sc, v3(0.0, 0.0, 0.20), scale=1.0, t_sec=t)
            for k_ng in range(9):
                ang = t * 0.9 + k_ng * (2.0 * math.pi / 9.0)
                sc.add_sphere(
                    v3(1.05 * math.cos(ang), 2.55 + 0.16 * math.sin(ang * 3.0), -0.95 + 1.05 * math.sin(ang)),
                    0.032, hex_rgb01("#FFE9A8"), roughness=0.1, emissive=(1.0, 0.9, 0.55),
                )
            a1 = _draw_slot(sc, sh, "hero", v3(-0.74, 0.0, 0.52),
                            yaw_deg=26.0, scale=0.86, style_mode=hero_style,
                            expression="happy", t_sec=t)
            a2 = _draw_slot(sc, sh, "buddy", v3(0.78, 0.0, 0.46),
                            yaw_deg=-26.0, scale=0.85, expression="happy",
                            t_sec=t + 0.6)
            a3 = _draw_slot(sc, sh, "leader", v3(0.92, 0.0, -0.86),
                            yaw_deg=-14.0, scale=0.80, expression="happy",
                            t_sec=t + 1.2)
            _draw_remaining_cast(sc, sh, [a1, a2, a3], t, back_z=-1.30)
            return sc.render()

        if preset == "story_hero_closeup":
            cam = Camera3D(
                pos=v3(lerp(-0.05, 0.04, e), lerp(1.86, 1.80, e), lerp(3.30, 2.90, e) * z_s),
                target=v3(0.0, 1.76, 0.0),
                fov_deg=33.0 * fov_s,
            )
            sc = Scene3D(
                W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
                bg_top=hex_rgb01("#8FD6F2"), bg_bot=hex_rgb01("#EDFBE4"),
                floor_y=0.0, floor_color=hex_rgb01("#B6E0A4"),
                key_dir=(-0.42, 0.76, 0.64), rim_color=hex_rgb01("#FFF9DE"),
            )
            draw_pine_tree(sc, v3(-1.55, 0.0, -2.10), scale=1.15)
            _draw_slot(sc, sh, "hero", v3(0.0, 0.0, 0.10),
                       yaw_deg=lerp(-14.0, 14.0, e), scale=1.02,
                       style_mode=hero_style, expression="happy", t_sec=t)
            return sc.render()

        # Default story preset: "story_happy_salute_end"
        sal_u = smoothstep((u - 0.18) / 0.30)
        cam = Camera3D(
            pos=v3(0.0, lerp(1.98, 1.90, e), lerp(8.05, 7.25, e) * z_s),
            target=v3(0.0, 1.38, 0.0),
            fov_deg=38.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
            bg_top=hex_rgb01("#8AD2F4"), bg_bot=hex_rgb01("#EFFADD"),
            floor_y=0.0, floor_color=hex_rgb01("#ACD99A"),
            key_dir=(-0.42, 0.78, 0.60), rim_color=hex_rgb01("#FFF7CE"),
        )
        draw_pine_tree(sc, v3(-1.85, 0.0, -2.05), scale=1.35)
        draw_pine_tree(sc, v3(1.82, 0.0, -2.00), scale=1.25)
        draw_camp_tent(sc, v3(-1.12, 0.0, -1.25), yaw_deg=22.0, scale=0.86)
        a1 = _draw_slot(sc, sh, "hero", v3(-0.52, 0.0, 0.28),
                        yaw_deg=12.0, scale=0.88, style_mode=hero_style,
                        expression="happy", salute=sal_u, wave=1.0 - sal_u, t_sec=t)
        a2 = _draw_slot(sc, sh, "buddy", v3(0.60, 0.0, 0.12),
                        yaw_deg=-16.0, scale=0.86, expression="happy",
                        salute=sal_u, wave=1.0 - sal_u, t_sec=t + 0.4)
        _draw_remaining_cast(sc, sh, [a1, a2], t)
        for k_sp in range(7):
            ang = t * 1.15 + k_sp * (2.0 * math.pi / 7.0)
            sc.add_sphere(
                v3(1.20 * math.cos(ang), 2.30 + 0.22 * math.sin(ang * 3.0 + 1.0), -0.60 + 1.10 * math.sin(ang)),
                0.034, COL["gold"], roughness=0.1, emissive=(0.60, 0.48, 0.08),
            )
        return sc.render()

    if preset == "disaster_wrong_badges":
        shake_x = math.sin(t * 26.0) * 0.032 * smoothstep((lt - 0.8) / 0.5) * (1.0 - smoothstep((u - 0.78) / 0.2))
        cam = Camera3D(
            pos=v3(lerp(0.0, 0.04, e) + shake_x, lerp(2.08, 1.96, e), lerp(8.45, 7.65, e) * z_s),
            target=v3(0.0, lerp(1.38, 1.44, e), 0.0),
            fov_deg=38.0 * fov_s,
            roll_deg=math.sin(t * 9.0) * 0.9 * (1.0 - 0.5 * u),
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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

    if preset == "closeup_chest_badges":
        cam = Camera3D(
            pos=v3(lerp(-0.08, 0.08, e), lerp(1.78, 1.72, e), lerp(4.35, 3.92, e) * z_s),
            target=v3(0.0, 1.62, 0.0),
            fov_deg=33.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
            bg_top=hex_rgb01("#8AC6F2"), bg_bot=hex_rgb01("#EAF6FE"),
            floor_y=0.0, floor_color=hex_rgb01("#CFE8FA"),
            key_dir=(-0.42, 0.72, 0.68), rim_color=hex_rgb01("#FFFFFF"),
        )
        draw_turntable_pedestal(sc, (0.0, 0.0), y_top=0.14, radius=1.04)
        draw_scout_figure(
            sc, v3(0.0, 0.14, 0.0),
            yaw_deg=lerp(-16.0, 16.0, e), scale=1.02,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            highlight_slots=("membership", "hongKong", "progressAward", "ventureAward", "award", "serviceStars", "nameTag"),
            s3d_custom=s3d_custom,
        )
        return sc.render()

    if preset == "closeup_right_sleeve":
        # rot_y(+72 deg) turns wearer's RIGHT sleeve (-X) directly toward camera (+Z)!
        cam = Camera3D(
            pos=v3(lerp(-0.06, 0.05, e), lerp(1.80, 1.74, e), lerp(4.20, 3.80, e) * z_s),
            target=v3(0.0, 1.66, 0.0),
            fov_deg=32.5 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
            bg_top=hex_rgb01("#88C8EE"), bg_bot=hex_rgb01("#EEF8FD"),
            floor_y=0.0, floor_color=hex_rgb01("#D2EAF9"),
            key_dir=(-0.38, 0.74, 0.68), rim_color=hex_rgb01("#FFFBE6"),
        )
        draw_turntable_pedestal(sc, (0.0, 0.0), y_top=0.14, radius=1.04)
        draw_scout_figure(
            sc, v3(0.0, 0.14, 0.0),
            yaw_deg=lerp(56.0, 82.0, e), scale=1.02,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            highlight_slots=("troop", "region", "district", "patrol", "meritorious"),
            s3d_custom=s3d_custom,
        )
        return sc.render()

    if preset == "closeup_left_sleeve":
        # rot_y(-70 deg) turns wearer's LEFT sleeve (+X) & upper sash directly toward camera (+Z)!
        cam = Camera3D(
            pos=v3(lerp(0.06, -0.05, e), lerp(1.78, 1.72, e), lerp(4.25, 3.85, e) * z_s),
            target=v3(0.0, 1.64, 0.0),
            fov_deg=33.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
            bg_top=hex_rgb01("#8AC6F2"), bg_bot=hex_rgb01("#EDF8FE"),
            floor_y=0.0, floor_color=hex_rgb01("#D1EAF9"),
            key_dir=(0.38, 0.74, 0.68), rim_color=hex_rgb01("#FFFBE6"),
        )
        draw_turntable_pedestal(sc, (0.0, 0.0), y_top=0.14, radius=1.04)
        draw_scout_figure(
            sc, v3(0.0, 0.14, 0.0),
            yaw_deg=lerp(-54.0, -80.0, e), scale=1.02,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
        )
        return sc.render()

    if preset == "leader_guide_explain":
        cam = Camera3D(
            pos=v3(lerp(-0.08, 0.06, e), lerp(2.00, 1.94, e), lerp(7.65, 7.05, e) * z_s),
            target=v3(0.0, 1.46, 0.0),
            fov_deg=37.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
            bg_top=hex_rgb01("#84C5DC"), bg_bot=hex_rgb01("#EEF9F6"),
            floor_y=0.0, floor_color=hex_rgb01("#D2ECE6"),
            key_dir=(-0.45, 0.76, 0.62), rim_color=hex_rgb01("#FFF8DC"),
        )
        draw_turntable_pedestal(sc, (-0.42, 0.18), y_top=0.13, radius=0.72)
        draw_scout_figure(
            sc, v3(-0.42, 0.13, 0.18),
            yaw_deg=lerp(-8.0, 26.0, e), scale=0.90,
            style_mode=hero_style, expression="happy",
            salute=0.0, badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
        )
        draw_leader_figure(sc, v3(0.66, 0.0, 0.02), yaw_deg=-24.0, scale=0.92, mood="praise", t_sec=t)
        return sc.render()

    if preset == "mom_turntable_sew":
        cam = Camera3D(
            pos=v3(lerp(-0.06, 0.04, e), 1.96, lerp(7.65, 7.05, e) * z_s),
            target=v3(0.0, 1.40, 0.0),
            fov_deg=37.0 * fov_s,
        )
        sc = Scene3D(
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
                show_sash=sec_has_sash if idx_p == 1 else (1.0 if s_name == "scout" else 0.0),
                section=s_name, gender="F" if idx_p == 2 and gen == "F" else gen,
                hat=sh_hat if idx_p == 1 else None,
                t_sec=t,
                s3d_custom=s3d_custom if idx_p == 1 else None,
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
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            badge_mode="correct", show_sash=sec_has_sash,
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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
            W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
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
            section=sec, gender=gen, hat=sh_hat, t_sec=t,
            s3d_custom=s3d_custom,
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
        W_px, H_px, _apply_camera_move(cam, sh.get("camera"), u, lt),
        bg_top=hex_rgb01("#7EC4CF"), bg_bot=hex_rgb01("#E8F8F5"),
        floor_y=0.0, floor_color=hex_rgb01("#CDEAE5"),
        key_dir=(-0.45, 0.76, 0.62), rim_color=hex_rgb01("#FFF8DC"),
    )
    draw_scout_figure(
        sc, v3(-0.98, 0.0, -0.18),
        yaw_deg=15.0, scale=0.82,
        style_mode="blocky", expression="happy",
        salute=salute_u, badge_mode="correct", show_sash=sec_has_sash,
        section=sec, gender=gen, hat=sh_hat, t_sec=t,
        s3d_custom=s3d_custom,
    )
    draw_turntable_pedestal(sc, (-0.02, 0.28), y_top=0.13, radius=0.70)
    draw_scout_figure(
        sc, v3(-0.02, 0.13, 0.28),
        yaw_deg=8.0, scale=0.88,
        style_mode="bobo", expression="happy",
        salute=salute_u, badge_mode="correct", show_sash=sec_has_sash,
        section=sec, gender=gen, hat=sh_hat, t_sec=t,
        s3d_custom=s3d_custom,
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

    # 4. Tiny「© SCOUT SYSTEM」水印（右下角・預設只喺片中間出現幾秒・有淡入淡出）
    wm = spec.get("watermark") or {}
    if bool(wm.get("enabled", True)):
        wm_text = str(wm.get("text") or "© SCOUT SYSTEM")
        total_sec = spec["total_frames"] / float(fps)
        show_sec = float(clamp(float(wm.get("show_sec") or 3.0), 1.0, max(1.0, total_sec)))
        t_now = frame_idx / float(fps)
        mid = total_sec / 2.0
        t0 = max(0.0, mid - show_sec / 2.0)
        t1 = min(total_sec, mid + show_sec / 2.0)
        if t0 - 1e-6 <= t_now <= t1 + 1e-6:
            fade = min(1.0, (t_now - t0) / 0.45, (t1 - t_now) / 0.45)
            fade = max(0.0, min(1.0, fade))
            alpha = int(round(96 + 118 * fade))
            wm_sz = 13 if aspect == "9:16" else 12
            f_wm = _font(wm_sz, bold=False)
            wb = draw.textbbox((0, 0), wm_text, font=f_wm)
            ww, wh = wb[2] - wb[0], wb[3] - wb[1]
            mg_x = 20 if aspect == "9:16" else 22
            mg_y = 30 if aspect == "9:16" else 22
            wtx = W_px - ww - mg_x - wb[0]
            wty = H_px - wh - mg_y - wb[1]
            draw.text((wtx + 1, wty + 1), wm_text, font=f_wm, fill=(8, 12, 20, int(alpha * 0.55)))
            draw.text((wtx, wty), wm_text, font=f_wm, fill=(255, 255, 255, alpha))

    return Image.alpha_composite(out, ui_layer).convert("RGB")


def _ensure_edge_tts_installed() -> bool:
    """Import edge_tts, auto-installing via pip once if missing on local Windows."""
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        print("[scout3d-runner] 首次啟用廣東話配音，正在自動安裝 edge-tts ...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "edge-tts"],
                check=False,
                timeout=90,
            )
            import edge_tts  # noqa: F401
            return True
        except Exception as exc:
            print(f"[scout3d-runner] 提示：無法自動安裝 edge-tts ({exc})，改用純 BGM 出片。")
            return False


def _load_mono_wav_44k(wav_path: Path) -> Tuple[np.ndarray, float]:
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_ch > 1:
        pcm = pcm.reshape(-1, n_ch).mean(axis=1)
    return pcm, len(pcm) / float(max(1, sr))


def _decode_and_trim_speech_wav(src_audio: Path, dst_wav: Path, sr: int = 44100) -> Tuple[np.ndarray, float]:
    """Decode TTS audio via bundled ffmpeg to 44.1kHz mono WAV and trim leading/trailing silence."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    tmp_raw_wav = dst_wav.with_suffix(".raw44k.wav")
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(src_audio),
        "-ac", "1",
        "-ar", str(sr),
        "-f", "wav",
        "-acodec", "pcm_s16le",
        str(tmp_raw_wav),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if res.returncode != 0 or not tmp_raw_wav.exists():
        raise RuntimeError(f"ffmpeg TTS decode failed ({res.returncode})")

    try:
        samples, _ = _load_mono_wav_44k(tmp_raw_wav)
    finally:
        tmp_raw_wav.unlink(missing_ok=True)

    if len(samples) == 0:
        raise RuntimeError("Decoded TTS audio is empty")

    active = np.flatnonzero(np.abs(samples) > 0.008)
    if len(active) > 0:
        i0 = max(0, int(active[0]) - int(0.03 * sr))
        i1 = min(len(samples), int(active[-1]) + int(0.07 * sr))
        samples = samples[i0:i1]

    fade_n = min(int(0.012 * sr), max(1, len(samples) // 8))
    if fade_n > 1:
        ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        samples[:fade_n] *= ramp
        samples[-fade_n:] *= ramp[::-1]

    peak = float(np.max(np.abs(samples)))
    if peak > 1e-4:
        samples = np.tanh((samples / peak) * 1.15) / math.tanh(1.15) * 0.90

    pcm16 = np.clip(samples * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(dst_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

    return samples.astype(np.float32), len(samples) / float(sr)


def _synthesize_single_tts_wav(
    text: str,
    voice: str,
    rate: str,
    cache_dir: Path,
    force: bool = False,
    engine: str = "edge",
    model: str = "",
    command: str = "",
) -> Optional[Tuple[Path, np.ndarray, float]]:
    """Synthesize or load cached Cantonese voiceover clip for a single shot."""
    cleaned = _clean_cantonese_tts_text(text)
    if not cleaned or voice == "none":
        return None
    engine = _norm_voice_engine(engine)

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"v2|{engine}|{voice}|{model}|{command}|{rate}|{cleaned}".encode("utf-8")).hexdigest()[:20]
    safe_voice = re.sub(r"[^a-zA-Z0-9_-]+", "_", voice or engine)
    dst_wav = cache_dir / f"vo_{safe_voice}_{key}.wav"

    if not force and dst_wav.exists() and dst_wav.stat().st_size > 256:
        try:
            samples, dur_s = _load_mono_wav_44k(dst_wav)
            if dur_s > 0.08:
                return dst_wav, samples, dur_s
        except Exception:
            pass

    if engine != "edge":
        tmp_ext = ".wav"
        try:
            with tempfile.NamedTemporaryFile(prefix="scout3d_tts_", suffix=tmp_ext, delete=False) as tf:
                tmp_audio = Path(tf.name)
            _run_external_tts(engine, cleaned, voice, model, command, tmp_audio)
            samples, dur_s = _decode_and_trim_speech_wav(tmp_audio, dst_wav)
            return dst_wav, samples, dur_s
        except Exception as exc:  # noqa: BLE001
            print(f"[scout3d-runner] 提示：{engine} 語音引擎失敗 ({exc})，該鏡頭改用純 BGM。")
            return None
        finally:
            try:
                tmp_audio.unlink(missing_ok=True)
            except Exception:
                pass

    if not _ensure_edge_tts_installed():
        return None

    import edge_tts

    last_err: Optional[Exception] = None
    for attempt in range(2):
        tmp_mp3: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(prefix="scout3d_tts_", suffix=".mp3", delete=False) as tf:
                tmp_mp3 = Path(tf.name)
            comm = edge_tts.Communicate(cleaned, voice, rate=rate)
            if hasattr(comm, "save_sync"):
                comm.save_sync(str(tmp_mp3))
            else:
                asyncio.run(comm.save(str(tmp_mp3)))
            samples, dur_s = _decode_and_trim_speech_wav(tmp_mp3, dst_wav)
            return dst_wav, samples, dur_s
        except Exception as exc:
            last_err = exc
            if attempt == 0:
                time.sleep(0.6)
        finally:
            if tmp_mp3 is not None:
                tmp_mp3.unlink(missing_ok=True)

    print(f"[scout3d-runner] 提示：廣東話配音連線失敗 ({last_err})，該鏡頭改用純 BGM。")
    return None


def prepare_episode_voiceovers(spec: Dict[str, Any], force: bool = False) -> Dict[int, np.ndarray]:
    """Synthesize Cantonese narration per shot and auto-extend shot durations so speech never clips."""
    voice = str(spec.get("voice") or "none")
    rate = str(spec.get("voice_rate") or "+6%")
    engine = _norm_voice_engine(spec.get("voice_engine"))
    model = str(spec.get("voice_model") or "")
    command = str(spec.get("tts_command") or "")
    if voice == "none":
        return {}

    tts_cache_dir = REPO_ROOT / ".cache" / "tts"
    fps = float(spec["fps"])
    vo_clips: Dict[int, np.ndarray] = {}
    expanded_any = False

    voice_label = CANTONESE_VOICES.get(voice, voice)
    has_narration = any(_clean_cantonese_tts_text(sh.get("narration", "")) for sh in spec["shots"])
    if has_narration:
        print(f"[scout3d-runner] 準備廣東話旁白配音：{voice_label} (語速 {rate}) ...")

    for sh in spec["shots"]:
        nar = str(sh.get("narration") or "")
        if not nar:
            continue
        res = _synthesize_single_tts_wav(nar, voice=voice, rate=rate, cache_dir=tts_cache_dir, force=force,
                                            engine=engine, model=model, command=command)
        if res is None:
            continue
        _, samples, tts_sec = res
        vo_clips[sh["index"]] = samples
        # Lock the cut to the REAL edge-tts speech length (0.14s lead-in + speech + 0.28s tail).
        # Both grow AND shrink so there is never 3-4s of dead air after the narration.
        if tts_sec > 0.0:
            locked_dur = max(2.2, 0.14 + tts_sec + 0.28)
            new_frames = max(12, int(round(locked_dur * fps)))
            if new_frames != sh["num_frames"]:
                sh["num_frames"] = new_frames
                sh["duration"] = new_frames / fps
                expanded_any = True

    if expanded_any:
        cur_f = 0
        for sh in spec["shots"]:
            sh["start_frame"] = cur_f
            sh["end_frame"] = cur_f + sh["num_frames"] - 1
            cur_f += sh["num_frames"]
        spec["total_frames"] = cur_f

    if vo_clips:
        print(
            f"[scout3d-runner] 已完成 {len(vo_clips)}/{len(spec['shots'])} 段廣東話配音"
            f"（片長 {spec['total_frames'] / fps:.1f}s）。"
        )
    return vo_clips


def _smooth_boxcar_1d(arr: np.ndarray, win: int) -> np.ndarray:
    if win <= 1 or len(arr) == 0:
        return arr
    csum = np.cumsum(np.insert(arr.astype(np.float64), 0, 0.0))
    half = win // 2
    idx = np.arange(len(arr))
    lo = np.clip(idx - half, 0, len(arr))
    hi = np.clip(idx - half + win, 1, len(arr))
    return ((csum[hi] - csum[lo]) / np.maximum(1, hi - lo)).astype(np.float32)


def synthesize_episode_audio(
    spec: Dict[str, Any],
    out_wav: Path,
    vo_clips: Optional[Dict[int, np.ndarray]] = None,
) -> Path:
    """Synthesize shot-synced stereo 44.1kHz BGM + UI pop chimes + ducked Cantonese voiceover."""
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
    has_vo = bool(vo_clips)
    bgm_target = 0.46 if has_vo else 0.72
    bgm_scale = min(1.8, bgm_target / peak)
    left *= bgm_scale
    right *= bgm_scale

    if vo_clips:
        vo_track = np.zeros(n, dtype=np.float32)
        speech_mask = np.zeros(n, dtype=np.float32)
        for sh in spec["shots"]:
            clip = vo_clips.get(sh["index"])
            if clip is None or len(clip) == 0:
                continue
            st0 = sh["start_frame"] / fps
            i0 = max(0, int(round((st0 + 0.14) * sr)))
            i1 = min(n, i0 + len(clip))
            if i1 <= i0:
                continue
            vo_track[i0:i1] += clip[: i1 - i0]
            m0 = max(0, i0 - int(0.08 * sr))
            m1 = min(n, i1 + int(0.16 * sr))
            speech_mask[m0:m1] = 1.0

        smooth_mask = _smooth_boxcar_1d(speech_mask, int(0.16 * sr))
        duck_gain = 1.0 - 0.66 * smooth_mask
        left = left * duck_gain + vo_track * 0.92
        right = right * duck_gain + vo_track * 0.92

    stereo = np.stack([left, right], axis=1)
    max_abs = float(np.max(np.abs(stereo)))
    if max_abs > 0.96:
        stereo *= 0.96 / max_abs
    pcm16 = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return out_wav


def _compute_audio_hash(spec: Dict[str, Any], plate_hash: str, active_vo_shots: Sequence[int]) -> str:
    h = hashlib.sha256()
    audio_spec = {
        "plate_hash": plate_hash,
        "bgm_mood": spec.get("bgm_mood"),
        "voice": spec.get("voice"),
        "voice_rate": spec.get("voice_rate"),
        "active_vo_shots": list(active_vo_shots),
        "shots": [
            {"index": s["index"], "num_frames": s["num_frames"], "narration": s.get("narration", "")}
            for s in spec["shots"]
        ],
    }
    h.update(json.dumps(audio_spec, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


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
        "s3d_custom": spec.get("s3d_custom"),
        "actor_skin": spec.get("actor_skin"),
        "story_section": spec.get("story_section"),
        "characters": spec.get("characters"),
        "camera": spec.get("camera"),
        "scene": spec.get("scene"),
        "shots": [
            {
                "preset": s["preset"],
                "num_frames": s["num_frames"],
                "section": s["section"],
                "story_section": s.get("story_section"),
                "actor_skin": s.get("actor_skin"),
                "gender": s["gender"],
                "hat": s.get("hat"),
                "show_sash": s.get("show_sash"),
                "style_mode": s["style_mode"],
                "show_ui_card": s["show_ui_card"],
                "trio_sections": s["trio_sections"],
                "camera": s.get("camera"),
                "scene": s.get("scene"),
                "cast": s.get("cast"),
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


def export_episode_contact_sheet(
    frames: Sequence[Image.Image],
    spec: Dict[str, Any],
    output_dir: Path,
    frame_indices: Optional[Sequence[int]] = None,
) -> Path:
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

    if frame_indices is not None and len(frame_indices) > 0:
        n_tiles = min(n_tiles, len(frames), len(frame_indices))
        src_slots = list(range(n_tiles))
        real_ids = [int(x) for x in list(frame_indices)[:n_tiles]]
    else:
        src_slots = [min(len(thumbs) - 1, round(i * (len(thumbs) - 1) / float(max(1, n_tiles - 1)))) for i in range(n_tiles)]
        real_ids = list(src_slots)

    for slot, src_idx in enumerate(src_slots):
        if src_idx < 0 or src_idx >= len(thumbs):
            continue
        r, c = slot // cols, slot % cols
        x, y = pad + c * (tw + pad), pad + r * (th + lh + pad)
        sheet.paste(thumbs[src_idx], (x, y))
        real_idx = real_ids[slot] if slot < len(real_ids) else src_idx
        sh = _find_shot(spec, real_idx)
        draw.text((x + 4, y + th + 4), f"F{real_idx:03d} {real_idx/fps:4.1f}s S{sh['index']}", fill=(235, 242, 250), font=font)

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
    vo_clips = prepare_episode_voiceovers(spec, force=force)
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

    # 串流解碼＋上字幕（逐格處理，唔會一次過食幾 GB RAM；長片都跑得順）
    n_tiles = min(24, total)
    sample_ids = sorted({
        min(total - 1, int(round(i * (total - 1) / float(max(1, n_tiles - 1)))))
        for i in range(n_tiles)
    })
    sampled_frames: Dict[int, Image.Image] = {}

    def _final_frame_iter():
        for i in range(total):
            with Image.open(plate_dir / f"plate_{i:04d}.png") as im:
                base = im.convert("RGB")
            out_im = overlay_episode_ui_and_subtitles(base, spec, i)
            if not fast_sub_only and i in sample_ids:
                sampled_frames[i] = out_im.copy()
            yield out_im

    audio_hash = _compute_audio_hash(spec, plate_hash, sorted(vo_clips.keys()))
    wav_path = REPO_ROOT / ".cache" / "audio" / f"{ep_id}_{audio_hash}.wav"
    if force or not wav_path.exists():
        synthesize_episode_audio(spec, wav_path, vo_clips=vo_clips)

    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_mp4_override or (output_dir / f"{ep_id}.mp4")
    encode_episode_mp4(_final_frame_iter(), spec, wav_path, out_mp4)
    print(f"[scout3d-runner] MP4 ready -> {out_mp4} ({out_mp4.stat().st_size / 1024:.1f} KB) in {time.time() - t_all:.2f}s.")

    if not fast_sub_only:
        cs = export_episode_contact_sheet(
            [sampled_frames[i] for i in sample_ids if i in sampled_frames],
            spec,
            output_dir,
            frame_indices=[i for i in sample_ids if i in sampled_frames],
        )
        print(f"[scout3d-runner] Contact sheet -> {cs}")

    return out_mp4


def cli_run_from_episode_script(raw_spec: Dict[str, Any], subtitle_lines: Dict[int, str]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=f"SCOUT 3D Episode: {raw_spec.get('episode_id', 'episode')}")
    parser.add_argument("--force", action="store_true", help="Force full 3D re-render ignoring clean-plate cache.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Fast subtitle swap (skip contact sheet).")
    parser.add_argument("--voice", type=str, default="", help="Cantonese TTS voice override (e.g. zh-HK-HiuMaanNeural, zh-HK-WanLungNeural, none).")
    parser.add_argument("--no-voice", action="store_true", help="Disable Cantonese voiceover and render BGM only.")
    parser.add_argument("--out", type=str, default="", help="Optional custom output .mp4 path.")
    args = parser.parse_args()
    spec_in = dict(raw_spec)
    if args.no_voice:
        spec_in["voice"] = "none"
    elif args.voice:
        spec_in["voice"] = args.voice
    out_p = Path(args.out) if args.out else None
    run_episode_dict(spec_in, subtitle_override=subtitle_lines, force=args.force, fast_sub_only=args.fast_sub_only, out_mp4_override=out_p)


def decode_b64_spec(b64_str: str) -> Dict[str, Any]:
    s = b64_str.strip()
    is_zlib = False
    if s.startswith("z_"):
        is_zlib = True
        s = s[2:]
    s = s.replace("+", "-").replace("/", "_")
    pad = "=" * ((4 - len(s) % 4) % 4)
    raw_bytes = base64.urlsafe_b64decode((s + pad).encode("ascii"))
    if is_zlib:
        try:
            raw_bytes = zlib.decompress(raw_bytes)
        except zlib.error:
            raw_bytes = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
    return json.loads(raw_bytes.decode("utf-8"))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Universal SCOUT 3D Episode Runner — paste `--b64 <payload>` directly in Windows CMD or pass `--spec <file.json>`!"
    )
    parser.add_argument("--b64", type=str, default="", help="URL-safe or standard Base64 UTF-8 JSON episode payload (zero-file CMD execution!).")
    parser.add_argument("--spec", type=str, default="", help="Path to an episode .json spec file.")
    parser.add_argument("--voice", type=str, default="", help="Cantonese TTS voice override (zh-HK-HiuMaanNeural, zh-HK-HiuGaaiNeural, zh-HK-WanLungNeural, none).")
    parser.add_argument("--no-voice", action="store_true", help="Disable Cantonese voiceover and render BGM only.")
    parser.add_argument("--tts-engine", default="", choices=["edge", "piper", "coqui", "command"], help="Local TTS engine (default: edge-tts).")
    parser.add_argument("--tts-model", default="", help="Model/voice path for piper (.onnx) or coqui model name.")
    parser.add_argument("--tts-command", default="", help="Custom TTS command for engine=command; placeholders: {out} {text_file} {text} {voice}.")
    parser.add_argument("--write-py", action="store_true", help="Also save a Git-ready `episodes/<episode_id>.py` file locally.")
    parser.add_argument("--only-write-py", action="store_true", help="Only write `episodes/<episode_id>.py` without rendering video.")
    parser.add_argument("--force", action="store_true", help="Force full 3D clean-plate re-render.")
    parser.add_argument("--fast-sub-only", action="store_true", help="Skip contact sheet generation.")
    parser.add_argument("--out", type=str, default="", help="Optional custom output MP4 path.")
    parser.add_argument("--list-presets", action="store_true", help="List available 3D shot presets and exit.")
    parser.add_argument("--list-cameras", action="store_true", help="List available camera moves and exit.")
    parser.add_argument("--list-scenes", action="store_true", help="List AI free-scene kinds and props, then exit.")
    parser.add_argument("--list-props", action="store_true", help="List AI free-scene prop ids, then exit.")
    parser.add_argument("--list-shapes", action="store_true", help="List free-form blueprint shapes and exit.")
    args = parser.parse_args()

    if args.list_presets:
        for k, desc in PRESET_CATALOG.items():
            print(f"  {k:24s} — {desc}")
        return

    if args.list_cameras:
        for k, desc in CAMERA_CATALOG.items():
            print(f"  {k:12s} — {desc}")
        return

    if args.list_scenes:
        print("AI 自由場景 scene kinds（每鏡揀一個）：")
        for k, desc in SCENE_KIND_CATALOG.items():
            defaults = ", ".join(_DEFAULT_SCENE_PROPS.get(k, [])) or "—"
            print(f"  {k:12s} — {desc}（預設道具：{defaults}）")
        print("\n用法：\"scene\": {\"kind\": \"space\", \"props\": [\"stars\", \"planet\", \"rocket\"], \"framing\": \"wide\", \"float\": true}")
        return

    if args.list_props:
        print("AI 自由場景 props（可選捷徑；真正自由用 scene.objects）：")
        for k, desc in PROP_CATALOG.items():
            print(f"  {k:12s} — {desc}")
        return

    if args.list_shapes:
        print("AI 自由場景 objects 基本形狀（可以砌任何場景）：")
        print("  sphere      球（size[0] = 半徑）")
        print("  ellipsoid   橢球（size = [rx, ry, rz]，可拉長／壓扁）")
        print("  box         圓角方塊（size = [半邊長 x, y, z]，bevel 控制圓角）")
        print("  capsule     膠囊（size = [半徑, 長度]，axis x/y/z）")
        print("  cylinder    圓柱（size = [半徑, 長度]，axis x/y/z）")
        print("  ring        環（size = [半徑, 粗幼]，tube 控制每節粗幼，count 控制密度）")
        print("\n每個 object 可用：pos, size, rot, color, glow, roughness, anim{bob,drift,spin,pulse}, repeat{count,area}")
        print("scene 層可用：objects, sky{top,bottom}, floor{color,y}|false, framing, float, cast")
        return

    if args.b64:
        raw_spec = decode_b64_spec(args.b64)
    elif args.spec:
        raw_spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        parser.error("Provide either `--b64 <BASE64_JSON>` (paste directly in CMD) or `--spec <episode.json>`.")
        return

    if args.no_voice:
        raw_spec["voice"] = "none"
    elif args.voice:
        raw_spec["voice"] = args.voice
    if args.tts_engine:
        raw_spec["voice_engine"] = args.tts_engine
    if args.tts_model:
        raw_spec["voice_model"] = args.tts_model
    if args.tts_command:
        raw_spec["tts_command"] = args.tts_command

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
