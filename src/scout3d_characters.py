"""Authoritative SCOUT3D Character, Garment & Programmatic Badge Engine for `makemovie`.

Driven 100% by `assets/scout3d/scout3d_rig_data.json` + official RGBA badge PNGs compiled from
`playerkousas-rgb/SCOUT3D` (`src/three/body.js`, `src/three/badgeLayout.js`, `src/data/*_rules_v1.0.json`).

Coordinate Convention (identical to SCOUT3D):
- Character stands on y = 0, facing +Z.
- +X = Wearer's LEFT (`穿著者左`, viewer's right when facing front).
- -X = Wearer's RIGHT (`穿著者右`, viewer's left when facing front).
- Metric scale: 1 cm in SCOUT3D = `CM_SCALE` (0.0156) world units (155 cm Scout = 2.42u).
"""

from __future__ import annotations

import base64
import json
import math
import re
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine3d import RGBf, Scene3D, hex_rgb01, normalize, rot_x, rot_y, rot_z, v3
from scout3d_badges import BadgeAssetError

REPO_ROOT = Path(__file__).resolve().parent.parent
SCOUT3D_ASSET_DIR = REPO_ROOT / "assets" / "scout3d"
RIG_JSON_PATH = SCOUT3D_ASSET_DIR / "scout3d_rig_data.json"
BADGE_DIR = SCOUT3D_ASSET_DIR / "badges"

# 155 cm Scout -> 2.418 world units (matches existing camera framing across all shots)
CM_SCALE: float = 0.0156

# Studio & prop color palette
COL: Dict[str, RGBf] = {
    "skin": hex_rgb01("#F1C6A2"),
    "blush": hex_rgb01("#F2A7A0"),
    "hair_dark": hex_rgb01("#241913"),
    "hair_mom": hex_rgb01("#4E3229"),
    "eye_dark": hex_rgb01("#231815"),
    "white": hex_rgb01("#FFFFFF"),
    "khaki": hex_rgb01("#E4D8B6"),
    "khaki_dark": hex_rgb01("#C9B98F"),
    "navy": hex_rgb01("#1C2D5A"),
    "maroon": hex_rgb01("#7B1E2B"),
    "yellow": hex_rgb01("#E9B425"),
    "scout_green": hex_rgb01("#1F8F45"),
    "scout_red": hex_rgb01("#D3262E"),
    "world_purple": hex_rgb01("#6242AD"),
    "district_blue": hex_rgb01("#2A6FBD"),
    "mom_sweater": hex_rgb01("#E6736E"),
    "mom_skirt": hex_rgb01("#36496E"),
    "pedestal_top": hex_rgb01("#2C3548"),
    "pedestal_rim": hex_rgb01("#1E2533"),
    "gold": hex_rgb01("#D8B23A"),
    "ok_green": hex_rgb01("#26B36B"),
    "warn_red": hex_rgb01("#E63946"),
    "sock": hex_rgb01("#F4F4F6"),
    "shoe": hex_rgb01("#202024"),
    "beret": hex_rgb01("#1F4A2C"),
    "beret_maroon": hex_rgb01("#8B2231"),
    "tent_green": hex_rgb01("#3D7A5A"),
    "tent_tan": hex_rgb01("#E6D2B5"),
    "book_a": hex_rgb01("#3A6EA5"),
    "book_b": hex_rgb01("#C8553D"),
    "book_c": hex_rgb01("#4A7C59"),
    "pages": hex_rgb01("#FAF3E3"),
}

# Supported SCOUT3D uniform sections (aligned 1:1 with `scout3d_rig_data.json`)
SECTION_STYLES: Dict[str, Dict[str, Any]] = {
    "grasshopper": {"zh": "小童軍", "sash_capable": False},
    "cub": {"zh": "幼童軍", "sash_capable": False},
    "scout": {"zh": "童軍", "sash_capable": True},
    "sea_scout": {"zh": "海童軍", "sash_capable": True},
    "air_scout": {"zh": "空童軍", "sash_capable": True},
    "venture": {"zh": "深資童軍", "sash_capable": False},
    "leader": {"zh": "成年領袖", "sash_capable": False},
    # 便服：唔著童軍制服（襯衫／褲由 outfit 決定），用 scout rig 嘅身形但冇領巾／帽／章
    "casual": {"zh": "便服", "sash_capable": False},
}

# Reusable 3D Character Presets ('人物角色設定檔') — configure once, reuse across unlimited episodes!
CHARACTER_PRESETS: Dict[str, Dict[str, Any]] = {
    "ming_scout": {
        "name": "阿明（童軍・左袖專科章）",
        "section": "scout",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": False,
    },
    "ming_scout_sash": {
        "name": "阿明（童軍・綠底紅邊專章帶）",
        "section": "scout",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 1.0,
        "hat": True,
    },
    "ching_scout_girl": {
        "name": "小晴（女童軍成員・孖辮・專章帶）",
        "section": "scout",
        "gender": "F",
        "style_mode": "bobo",
        "show_sash": 1.0,
        "hat": False,
    },
    "lok_cub": {
        "name": "樂樂（幼童軍・黃領巾綠邊）",
        "section": "cub",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": True,
    },
    "yau_grasshopper": {
        "name": "悠悠（小童軍・橙色上衣）",
        "section": "grasshopper",
        "gender": "F",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": False,
    },
    "hin_venture": {
        "name": "阿軒（深資童軍・紫紅肩章貝雷帽）",
        "section": "venture",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": True,
    },
    "hoi_sea_scout": {
        "name": "阿海（海童軍・白色制服水手帽）",
        "section": "sea_scout",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": True,
    },
    "tin_air_scout": {
        "name": "阿天（空童軍・淺藍制服）",
        "section": "air_scout",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": True,
    },
    "sir_leader": {
        "name": "陳領袖（成年領袖・SL肩章・右袋香港章）",
        "section": "leader",
        "gender": "M",
        "style_mode": "bobo",
        "show_sash": 0.0,
        "hat": True,
    },
}

_RIG_CACHE: Optional[Dict[str, Any]] = None
_TEX_CACHE: Dict[str, np.ndarray] = {}


def _get_rig_data() -> Dict[str, Any]:
    global _RIG_CACHE
    if _RIG_CACHE is None:
        with open(RIG_JSON_PATH, "r", encoding="utf-8") as f:
            _RIG_CACHE = json.load(f)
    return _RIG_CACHE


def _ordinal_en(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suf = "TH"
    else:
        suf = {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{suf}"


def _load_badge_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        from spec_loader import ensure_font_path
        fp = ensure_font_path()
        if fp:
            return ImageFont.truetype(fp, size)
    except Exception:
        pass
    return ImageFont.load_default()


def decode_s3d_code(raw_val: Union[str, Dict[str, Any], None]) -> Optional[Dict[str, Any]]:
    """Decode a SCOUT 3D outfit/badge code (`S3D1_<zlib_b64>`, `S3D_<b64>`, JSON string, or dict)."""
    if raw_val is None:
        return None
    if isinstance(raw_val, dict):
        return raw_val if raw_val else None
    s = str(raw_val).strip()
    if not s:
        return None
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    is_zlib = False
    if s.startswith("S3D1_"):
        is_zlib = True
        s = s[5:]
    elif s.startswith("S3D_"):
        s = s[4:]
    else:
        return None

    s = s.replace("+", "-").replace("/", "_")
    pad = "=" * ((4 - len(s) % 4) % 4)
    raw_bytes = base64.urlsafe_b64decode((s + pad).encode("ascii"))
    if is_zlib:
        try:
            raw_bytes = zlib.decompress(raw_bytes)
        except zlib.error:
            raw_bytes = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
    obj = json.loads(raw_bytes.decode("utf-8"))
    return obj if isinstance(obj, dict) else None


def _render_dynamic_badge_image(dyn: Dict[str, Any], shape: str = "rect") -> Image.Image:
    kind = str(dyn.get("kind") or "")
    if kind == "troopTape":
        no_raw = str(dyn.get("no") or "1").strip()
        try:
            no_int = max(1, int("".join(ch for ch in no_raw if ch.isdigit()) or "1"))
        except ValueError:
            no_int = 1
        im = Image.new("RGBA", (320, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((2, 2, 317, 93), radius=18, fill=(182, 28, 36, 255), outline=(238, 196, 68, 255), width=5)
        f_zh = _load_badge_font(32)
        f_en = _load_badge_font(22)
        zh_txt = dyn.get("zhText") or f"香港第 {no_int} 旅"
        en_txt = dyn.get("enText") or f"{_ordinal_en(no_int)} HONG KONG"
        d.text((160, 30), str(zh_txt), font=f_zh, fill=(250, 218, 92, 255), anchor="mm")
        d.text((160, 68), str(en_txt), font=f_en, fill=(250, 218, 92, 255), anchor="mm")
        return im

    if kind == "merit":
        year = str(dyn.get("year") or "2025")
        base_p = BADGE_DIR / "meritorious_base_blue.png"
        if base_p.is_file():
            im = Image.open(base_p).convert("RGBA").resize((220, 220), Image.Resampling.LANCZOS)
        else:
            im = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse((8, 8, 212, 212), fill=(26, 68, 148, 255), outline=(238, 196, 68, 255), width=8)
        d = ImageDraw.Draw(im)
        f_yr = _load_badge_font(38)
        d.text((110, 156), year, font=f_yr, fill=(252, 216, 86, 255), anchor="mm")
        return im

    if kind == "nameTag":
        im = Image.new("RGBA", (280, 76), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((2, 2, 277, 73), radius=10, fill=(24, 42, 84, 255), outline=(245, 245, 248, 255), width=4)
        txt = str(dyn.get("zh") or dyn.get("en") or "SCOUT")[:10]
        d.text((140, 38), txt, font=_load_badge_font(30), fill=(255, 255, 255, 255), anchor="mm")
        return im

    # Clean embroidered fallback emblem when offline and PNG not yet cached
    im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shape == "circle":
        d.ellipse((6, 6, 174, 174), fill=(31, 107, 74, 255), outline=(232, 196, 78, 255), width=10)
    else:
        d.rounded_rectangle((6, 6, 174, 174), radius=24, fill=(31, 107, 74, 255), outline=(232, 196, 78, 255), width=10)
    lbl = str(dyn.get("label") or "章")[:3]
    d.text((90, 92), lbl, font=_load_badge_font(44), fill=(255, 248, 220, 255), anchor="mm")
    return im


def _get_badge_rgba(
    rel_file: str,
    dyn: Optional[Dict[str, Any]] = None,
    shape: str = "rect",
    label_zh: str = "",
) -> Optional[np.ndarray]:
    if dyn and isinstance(dyn, dict) and dyn.get("kind") in ("troopTape", "merit", "nameTag"):
        dyn_key = "__dyn__:" + json.dumps(dyn, sort_keys=True, ensure_ascii=False)
        if dyn_key in _TEX_CACHE:
            return _TEX_CACHE[dyn_key]
        im = _render_dynamic_badge_image(dyn, shape=shape)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        _TEX_CACHE[dyn_key] = arr
        return arr

    if not rel_file:
        return None
    clean = rel_file.lstrip("/")
    if clean.startswith("badges/"):
        clean = clean[len("badges/") :]
    if clean in _TEX_CACHE:
        return _TEX_CACHE[clean]
    full = BADGE_DIR / clean
    # v3.5：SCOUT 3D 官方徽章已經全部鏡像入 assets/scout3d/badges，只讀本地。
    # 以前呢度會即場上網下載，網絡唔通就會寫入錯誤頁，之後每次 render 都炸。
    if not full.is_file():
        raise BadgeAssetError(
            f"[scout3d-characters] ✗ 缺少徽章圖：{clean}\n"
            f"  期望位置：{full}\n"
            f"  章庫已內置，請執行：git checkout -- assets/scout3d/badges\n"
            f"  或者跑：python src/check_badge_assets.py 睇缺咩"
        )
    try:
        img = Image.open(full).convert("RGBA")
    except Exception as exc:
        raise BadgeAssetError(
            f"[scout3d-characters] ✗ 徽章圖損壞（唔係正常 PNG）：{clean}\n"
            f"  檔案：{full}（{full.stat().st_size} bytes）\n"
            f"  修復：git checkout -- assets/scout3d/badges"
        ) from exc
    arr = np.asarray(img, dtype=np.float32) / 255.0
    _TEX_CACHE[clean] = arr
    return arr


def _darken_rgb(col: RGBf, factor: float = 0.88) -> RGBf:
    return (col[0] * factor, col[1] * factor, col[2] * factor)


def resolve_character_preset(preset: Union[str, Dict[str, Any], Path, None]) -> Dict[str, Any]:
    """Load a reusable 3D character preset by ID, dict, or `.json` file path."""
    if preset is None:
        return {}
    if isinstance(preset, dict):
        base_id = preset.get("preset")
        merged = dict(CHARACTER_PRESETS.get(base_id, {})) if base_id else {}
        merged.update(preset)
        return merged
    if isinstance(preset, Path) or (isinstance(preset, str) and preset.endswith(".json")):
        p = Path(preset)
        if not p.is_absolute():
            p = REPO_ROOT / p
        with open(p, "r", encoding="utf-8") as f:
            return resolve_character_preset(json.load(f))
    if isinstance(preset, str):
        return dict(CHARACTER_PRESETS.get(preset, {}))
    return {}


def _select_rig_bundle(section: str, gender: str, use_sash: bool) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    data = _get_rig_data()["sections"]
    sec = section.lower().strip()
    if sec not in data:
        sec = "scout"
    gen = "girl" if str(gender).upper().startswith(("F", "G")) else "boy"
    sec_entry = data[sec]
    gen_entry = sec_entry["genders"][gen]
    if (not use_sash) and (gen_entry.get("placementsNoSash") is not None):
        badges = gen_entry["placementsNoSash"]["badges"]
    else:
        badges = gen_entry["placements"]["badges"]
    return sec_entry["variant"], gen_entry, badges


def draw_turntable_pedestal(
    sc: Scene3D, center_xz: Tuple[float, float] = (0.0, 0.0), y_top: float = 0.16, radius: float = 1.05
) -> None:
    """Signature SCOUT3D Hero-Forge dark circular 3D turntable base."""
    cx, cz = center_xz
    sc.add_floor_shadow(cx, cz, radius * 1.28, strength=0.34)
    sc.add_cylinder(v3(cx, 0.0, cz), v3(cx, y_top * 0.58, cz), radius * 1.06, COL["pedestal_rim"], roughness=0.38)
    sc.add_cylinder(v3(cx, y_top * 0.55, cz), v3(cx, y_top, cz), radius, COL["pedestal_top"], roughness=0.34)
    sc.add_cylinder(
        v3(cx, y_top - 0.012, cz),
        v3(cx, y_top + 0.004, cz),
        radius * 0.92,
        hex_rgb01("#4FA8E8"),
        roughness=0.25,
    )
    sc.add_cylinder(
        v3(cx, y_top - 0.010, cz),
        v3(cx, y_top + 0.006, cz),
        radius * 0.88,
        COL["pedestal_top"],
        roughness=0.36,
    )


def get_scout_badge_slots_local(section: str = "scout", gender: str = "M", sash: bool = False) -> List[Dict[str, Any]]:
    """Return authoritative SCOUT3D badge slots in world-scaled local coordinates."""
    _, gen_entry, badges = _select_rig_bundle(section, gender, sash)
    L = gen_entry["layout"]
    out: List[Dict[str, Any]] = []
    for p in badges:
        mount = p.get("mount", "torso")
        if mount in ("r", "l"):
            sgn = -1.0 if mount == "r" else +1.0
            alp = p["armLocalPos"]
            pos_cm = v3(sgn * L["armX"] + alp[0], L["shoulderY"] + alp[1], alp[2])
        else:
            pos_cm = v3(float(p["x"]), float(p["y"]), float(p["z"]))
        out.append(
            {
                "id": p["key"],
                "slot": p["id"],
                "pos": pos_cm * CM_SCALE,
                "w": float(p["w"]) * CM_SCALE,
                "h": float(p["h"]) * CM_SCALE,
                "mount": mount,
                "facing": p.get("facing", "front"),
                "rotZ": float(p.get("rotZ", 0.0)),
                "file": p.get("art"),
            }
        )
    return out


def get_wrong_messy_badges_local() -> List[Dict[str, Any]]:
    """Intentionally hilarious misplaced badges ONLY for 'Before SCOUT 3D' disaster gag shots!"""
    return [
        {
            "pos": v3(0.04, 1.44, 0.145),     # Troop tape stuck crooked right on the belly!
            "nrm": v3(0.0, 0.0, 1.0),
            "u_right": v3(0.94, -0.34, 0.0),
            "v_up": v3(0.34, 0.94, 0.0),
            "w": 0.145,
            "h": 0.040,
            "file": "handbook_example_troop.png",
        },
        {
            "pos": v3(0.33, 1.84, 0.01),      # Patrol badge sewed upside-down onto WRONG (left) sleeve!
            "nrm": v3(1.0, 0.0, 0.0),
            "u_right": v3(0.0, 0.0, 1.0),
            "v_up": v3(0.0, -1.0, 0.0),
            "w": 0.075,
            "h": 0.036,
            "file": "patrols/badger.png",
        },
        {
            "pos": v3(-0.14, 1.34, 0.145),    # World Membership badge way down near right waist!
            "nrm": v3(0.0, 0.0, 1.0),
            "u_right": v3(0.96, 0.28, 0.0),
            "v_up": v3(-0.28, 0.96, 0.0),
            "w": 0.072,
            "h": 0.072,
            "file": "world_membership.png",
        },
        {
            "pos": v3(-0.10, 0.98, 0.12),     # Hong Kong badge sewed crooked onto shorts knee!!
            "nrm": v3(0.0, 0.0, 1.0),
            "u_right": v3(0.92, -0.38, 0.0),
            "v_up": v3(0.38, 0.92, 0.0),
            "w": 0.068,
            "h": 0.092,
            "file": "hong_kong_badge.png",
        },
    ]


def _slot_progress(slot_key: str, slot_id: str, badge_progress: Optional[Dict[str, float]]) -> float:
    """Resolve animation progress for both native SCOUT3D slot IDs and legacy EP.01 keys."""
    if badge_progress is None:
        return 1.0
    if slot_key in badge_progress:
        return float(badge_progress[slot_key])
    if slot_id in badge_progress:
        return float(badge_progress[slot_id])

    if slot_id in ("membership", "serviceStars", "nameTag"):
        return float(badge_progress.get("membership", 1.0))
    if slot_id in ("hongKong", "emblemBauhinia", "ventureLink", "scoutLink", "progressAward", "ventureAward", "award"):
        return float(badge_progress.get("link_award", badge_progress.get("membership", 1.0)))
    if slot_id in ("troop", "epaulette", "meritorious"):
        return float(badge_progress.get("troop_tape", 1.0))
    if slot_id in ("region", "district"):
        return float(badge_progress.get("district", 1.0))
    if slot_id in ("patrol", "instructor", "dragonAward", "chiefScoutAward", "tribe", "leadership"):
        return float(badge_progress.get("patrol", 1.0))
    if slot_id.startswith("prof") or slot_key.startswith("prof") or slot_id in ("progress", "activity", "challenge"):
        digits = "".join(ch for ch in slot_key if ch.isdigit())
        idx = max(0, int(digits) - 1) if digits else 0
        p1 = badge_progress.get("prof_sleeve_1", 1.0)
        p2 = badge_progress.get("prof_sleeve_2", p1)
        base = p1 if idx < 4 else p2
        return float(max(0.0, min(1.0, base * 1.15 - idx * 0.02)))
    return 1.0


def _draw_headwear(
    sc: Scene3D,
    W,
    WV,
    WN,
    R: np.ndarray,
    S_cm,
    head: Dict[str, float],
    variant: Dict[str, Any],
    is_blocky: bool,
) -> None:
    """Draw authentic SCOUT3D headwear (`beret`, `cubCap`, `seaCap`, `cap`) + official RGBA cap badge."""
    hat_type = variant.get("hat")
    if not hat_type:
        return
    hat_col = hex_rgb01(variant.get("hatColor") or "#1F4A2C")
    cap_tex = _get_badge_rgba(variant.get("capBadge") or "")

    top_y = head["y"] + head["h"]
    hw = head["w"] * 0.5
    hd = head["d"] * 0.5
    hz = head["z"]

    if hat_type == "beret":
        # Authentic HK Scout Beret tilted slightly right (-X), cap badge over left eye (+X)
        b_rot = R @ rot_z(6.5)
        if is_blocky:
            sc.add_rounded_box(
                W(-0.7, top_y + 1.1, hz + 0.2),
                (S_cm(hw + 1.6), S_cm(2.5), S_cm(hd + 1.5)),
                S_cm(0.85),
                hat_col,
                rot=b_rot,
                roughness=0.52,
            )
        else:
            sc.add_ellipsoid(
                W(-0.7, top_y + 1.1, hz + 0.2),
                (S_cm(hw + 2.1), S_cm(2.9), S_cm(hd + 1.9)),
                hat_col,
                rot=b_rot,
                roughness=0.50,
            )
        sc.add_rounded_box(
            W(0.0, top_y - 0.65, hz + 0.15),
            (S_cm(hw + 0.85), S_cm(0.75), S_cm(hd + 0.85)),
            S_cm(0.38 if is_blocky else 1.2),
            COL["shoe"],
            rot=R,
            roughness=0.38,
        )
        if cap_tex is not None:
            sc.add_textured_patch_3d(
                WV(v3(2.8, top_y + 1.0, hz + hd + 1.85)),
                WN(v3(0.14, 0.05, 0.99)),
                WN(v3(0.99, 0.0, -0.14)),
                WN(v3(0.0, 1.0, -0.05)),
                S_cm(3.4),
                S_cm(3.8),
                cap_tex,
                lift=S_cm(0.08),
            )
    elif hat_type in ("cubCap", "cap"):
        sc.add_ellipsoid(
            W(0.0, top_y + 0.9, hz),
            (S_cm(hw + 1.3), S_cm(2.9), S_cm(hd + 1.3)),
            hat_col,
            rot=R,
            roughness=0.48,
        )
        sc.add_rounded_box(
            W(0.0, top_y - 0.55, hz + hd + 2.2),
            (S_cm(hw * 0.80), S_cm(0.50), S_cm(3.0)),
            S_cm(0.42),
            hat_col,
            rot=R @ rot_x(10.0),
            roughness=0.48,
        )
        if cap_tex is not None:
            sc.add_textured_patch_3d(
                WV(v3(0.0, top_y + 1.25, hz + hd + 1.35)),
                WN(v3(0.0, 0.08, 1.0)),
                WN(v3(1.0, 0.0, 0.0)),
                WN(v3(0.0, 1.0, -0.08)),
                S_cm(3.4),
                S_cm(3.4),
                cap_tex,
                lift=S_cm(0.08),
            )
    elif hat_type == "seaCap":
        # White-top Sea Scout cap with dark navy tally band (`sea_scout_cap_tally.png`) + black peak
        sc.add_rounded_box(
            W(0.0, top_y - 0.35, hz),
            (S_cm(hw + 0.95), S_cm(1.1), S_cm(hd + 0.95)),
            S_cm(0.45 if is_blocky else 1.35),
            COL["navy"],
            rot=R,
            roughness=0.42,
        )
        sc.add_ellipsoid(
            W(0.0, top_y + 1.65, hz + 0.15),
            (S_cm(hw + 1.9), S_cm(2.1), S_cm(hd + 1.9)),
            hat_col,
            rot=R,
            roughness=0.40,
        )
        sc.add_rounded_box(
            W(0.0, top_y - 0.95, hz + hd + 2.1),
            (S_cm(hw * 0.78), S_cm(0.44), S_cm(2.6)),
            S_cm(0.35),
            COL["shoe"],
            rot=R @ rot_x(12.0),
            roughness=0.25,
        )
        if cap_tex is not None:
            sc.add_textured_patch_3d(
                WV(v3(0.0, top_y - 0.30, hz + hd + 1.05)),
                WN(v3(0.0, 0.0, 1.0)),
                WN(v3(1.0, 0.0, 0.0)),
                WN(v3(0.0, 1.0, 0.0)),
                S_cm(9.2),
                S_cm(1.6),
                cap_tex,
                lift=S_cm(0.08),
            )


def draw_scout_figure(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    style_mode: str = "bobo",        # "bobo" (Smooth Rounded 3D) or "blocky" (SCOUT3D Blocky 3D)
    expression: str = "happy",       # "happy" | "nervous" | "surprised" | "proud"
    salute: float = 0.0,             # 0.0 = relaxed arms, 1.0 = crisp 3-finger HK Scout salute!
    badge_mode: str = "correct",     # "none" | "wrong" | "correct" | "animated"
    badge_progress: Optional[Dict[str, float]] = None,
    show_sash: float = 0.0,          # 0..1 visibility of Scout green/red Proficiency Sash
    section: str = "scout",          # "grasshopper"|"cub"|"scout"|"sea_scout"|"air_scout"|"venture"|"leader"
    gender: str = "M",               # "M" | "F"
    wave: float = 0.0,               # 0..1 cheerful left-hand wave
    t_sec: float = 0.0,
    hat: Optional[bool] = None,
    preset: Union[str, Dict[str, Any], Path, None] = None,
    highlight_slots: Optional[Sequence[str]] = None,
    s3d_custom: Optional[Dict[str, Any]] = None,
    actor_skin: str = "human",       # "human" | "ai_robot"
    outfit: Optional[Dict[str, Any]] = None,   # 便服設定（section="casual" 時使用）
) -> None:
    """Draw an authentic 3D Hong Kong Scout character using exact SCOUT3D rules & RGBA badges."""
    if preset is not None:
        cfg = resolve_character_preset(preset)
        section = str(cfg.get("section", section))
        gender = str(cfg.get("gender", gender))
        style_mode = str(cfg.get("style_mode", style_mode))
        show_sash = float(cfg.get("show_sash", show_sash))
        if hat is None and "hat" in cfg:
            hat = bool(cfg["hat"])
        if s3d_custom is None and cfg.get("s3d_custom"):
            s3d_custom = decode_s3d_code(cfg.get("s3d_custom"))

    custom_cfg = decode_s3d_code(s3d_custom) if s3d_custom is not None else None
    if custom_cfg:
        raw_sec = str(custom_cfg.get("rigSection") or custom_cfg.get("section") or section).lower().strip()
        raw_var = str(custom_cfg.get("variant") or "").lower().strip()
        if raw_sec == "scout" and raw_var == "sea":
            section = "sea_scout"
        elif raw_sec == "scout" and raw_var == "air":
            section = "air_scout"
        elif raw_sec == "rover":
            section = "venture"
        elif raw_sec in SECTION_STYLES:
            section = raw_sec
        if custom_cfg.get("gender"):
            g_str = str(custom_cfg["gender"]).upper()
            gender = "F" if g_str.startswith(("F", "G")) else "M"
        if "hat" in custom_cfg and custom_cfg["hat"] is not None:
            hat = bool(custom_cfg["hat"])
        if "sash" in custom_cfg and custom_cfg["sash"] is not None:
            show_sash = 1.0 if bool(custom_cfg["sash"]) else 0.0

    sec = section.lower().strip()
    sash_supported = sec in ("scout", "sea_scout", "air_scout")
    sash_amt = float(max(0.0, min(1.0, show_sash))) if sash_supported else 0.0
    use_sash_layout = sash_supported and (sash_amt > 0.05)

    base_variant, gen_entry, default_badges = _select_rig_bundle(sec, gender, use_sash_layout)
    variant = dict(base_variant)
    badges = default_badges

    # 便服模式：換色、除帽、除領巾、除章（保留童軍 rig 嘅身形同表情）
    casual_mode = (sec == "casual")
    if casual_mode:
        of = outfit if isinstance(outfit, dict) else {}
        style = str(of.get("style") or "tee").lower().strip()
        top = str(of.get("top") or of.get("color") or "").strip()
        bottom = str(of.get("bottom") or "").strip()
        accent = str(of.get("accent") or "").strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", top):
            top = "#5B8DEF"
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", bottom):
            bottom = "#31456B" if style != "dress" else top
        variant["shirt"] = top
        variant["leg"] = bottom
        variant["sock"] = "#F4F4F6"
        variant["shoe"] = "#23262B"
        variant["belt"] = None
        variant["hat"] = None
        variant["longPants"] = True
        if re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            variant["buckle"] = accent
        hat = False
        show_sash = 0.0
        if badge_mode in ("correct", "animated"):
            badge_mode = "none"

    custom_neck_border: Optional[str] = None
    if custom_cfg:
        cols = custom_cfg.get("colors") or {}
        for src_k, dst_k in (
            ("shirt", "shirt"),
            ("leg", "leg"),
            ("sock", "sock"),
            ("shoe", "shoe"),
            ("belt", "belt"),
            ("buckle", "buckle"),
            ("hatColor", "hatColor"),
            ("hatType", "hat"),
            ("neckerMain", "necker"),
            ("woggle", "woggle"),
        ):
            val = cols.get(src_k)
            if isinstance(val, str) and val.strip():
                variant[dst_k] = val.strip()
        if "longPants" in cols and cols["longPants"] is not None:
            variant["longPants"] = bool(cols["longPants"])
        nb = cols.get("neckerBorder")
        if isinstance(nb, str) and nb.startswith("#"):
            custom_neck_border = nb.strip()
        if isinstance(custom_cfg.get("badges"), list) and len(custom_cfg["badges"]) > 0:
            badges = custom_cfg["badges"]

    L = gen_entry["layout"]
    B = L["B"]
    strap = gen_entry.get("strap")
    sash_cfg = gen_entry.get("sash")

    is_blocky = style_mode == "blocky"
    is_robot = str(actor_skin or "human").lower() in ("ai_robot", "robot", "ai")
    is_girl = str(gender).upper().startswith(("F", "G"))
    wear_hat = False if is_robot else (bool(hat) if hat is not None else (sec in ("venture", "leader")))
    c_limb = hex_rgb01("#DCE6F2") if is_robot else COL["skin"]

    R = rot_y(yaw_deg)
    k = CM_SCALE * scale

    def W(cx: float, cy: float, cz: float) -> np.ndarray:
        return base_pos + (R @ v3(cx * k, cy * k, cz * k))

    def WV(vec_cm: np.ndarray) -> np.ndarray:
        return base_pos + (R @ (vec_cm * k))

    def WN(n_local: np.ndarray) -> np.ndarray:
        return normalize(R @ n_local)

    S_cm = lambda cm_val: float(cm_val) * k

    c_shirt = hex_rgb01(variant["shirt"])
    c_pocket = _darken_rgb(c_shirt, 0.90)
    c_bottom = hex_rgb01(variant["leg"])
    c_sock = hex_rgb01(variant["sock"])
    c_shoe = hex_rgb01(variant["shoe"])
    c_belt = hex_rgb01(variant["belt"]) if variant.get("belt") else None
    c_buckle = hex_rgb01(variant.get("buckle") or "#C9CCD1")
    c_necker = hex_rgb01(variant["necker"])
    if custom_neck_border:
        c_neck_trim = (
            hex_rgb01(custom_neck_border)
            if custom_neck_border.lower() != str(variant["necker"]).lower()
            else None
        )
    else:
        c_neck_trim = hex_rgb01("#1F7A3F") if sec == "cub" else (hex_rgb01("#F5C518") if sec == "grasshopper" else None)
    c_woggle = hex_rgb01(variant["woggle"])

    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S_cm(B["torso"]["w"] * 1.15), strength=0.26)

    # =========================================================================
    # 1. SHOES, SOCKS, LEGS & SHORTS / CULOTTES / TROUSERS (Exact SCOUT3D `B`)
    # =========================================================================
    leg = B["leg"]
    shoe = B["shoe"]
    leg_hw = leg["w"] * 0.5
    leg_hd = leg["d"] * 0.5
    leg_x_abs = float(L["legX"])
    long_trousers = bool(variant.get("longPants")) and not (is_girl and B.get("skirtBottom") is not None)
    has_skirt = is_girl and (sec != "grasshopper")

    for side in (-1.0, 1.0):
        lx = side * leg_x_abs
        if is_blocky:
            sc.add_rounded_box(
                W(lx, shoe["h"] * 0.5, shoe["z"]),
                (S_cm(shoe["w"] * 0.5), S_cm(shoe["h"] * 0.5), S_cm(shoe["d"] * 0.5)),
                S_cm(0.45),
                c_shoe,
                rot=R,
                roughness=0.40,
            )
        else:
            sc.add_ellipsoid(
                W(lx, shoe["h"] * 0.52, shoe["z"] + 0.3),
                (S_cm(shoe["w"] * 0.54), S_cm(shoe["h"] * 0.56), S_cm(shoe["d"] * 0.54)),
                c_shoe,
                rot=R,
                roughness=0.36,
            )

        if long_trousers:
            y0, y1 = shoe["h"] * 0.85, leg["top"] + 0.8
            sc.add_rounded_box(
                W(lx, 0.5 * (y0 + y1), 0.0),
                (S_cm(leg_hw + 0.25), S_cm(0.5 * (y1 - y0)), S_cm(leg_hd + 0.25)),
                S_cm(0.48 if is_blocky else 1.65),
                c_bottom,
                rot=R,
                roughness=0.55,
            )
        else:
            leg_span = leg["top"] - leg["y"]
            sock_top = leg["y"] + leg_span * 0.36
            shorts_bot = float(B.get("skirtBottom") or (leg["top"] - leg_span * 0.32))
            if is_blocky:
                sc.add_rounded_box(
                    W(lx, 0.5 * (leg["y"] + sock_top), 0.0),
                    (S_cm(leg_hw * 0.92), S_cm(0.5 * (sock_top - leg["y"])), S_cm(leg_hd * 0.92)),
                    S_cm(0.4),
                    c_sock,
                    rot=R,
                    roughness=0.58,
                )
                sc.add_rounded_box(
                    W(lx, 0.5 * (sock_top + shorts_bot), 0.0),
                    (S_cm(leg_hw * 0.88), S_cm(0.5 * (shorts_bot - sock_top)), S_cm(leg_hd * 0.88)),
                    S_cm(0.4),
                    c_limb,
                    rot=R,
                    roughness=0.50,
                )
            else:
                sc.add_capsule(W(lx, leg["y"] + 0.8, 0.0), W(lx, sock_top, 0.0), S_cm(leg_hw * 0.86), c_sock, roughness=0.58)
                sc.add_capsule(W(lx, sock_top - 0.4, 0.0), W(lx, shorts_bot + 1.2, 0.0), S_cm(leg_hw * 0.84), c_limb, roughness=0.50)

            if not has_skirt:
                sc.add_rounded_box(
                    W(lx, 0.5 * (shorts_bot + leg["top"]), 0.0),
                    (S_cm(leg_hw + 0.35), S_cm(0.5 * (leg["top"] - shorts_bot) + 0.3), S_cm(leg_hd + 0.35)),
                    S_cm(0.48 if is_blocky else 1.55),
                    c_bottom,
                    rot=R,
                    roughness=0.55,
                )

    tor = B["torso"]
    tor_hw = tor["w"] * 0.5
    tor_hh = tor["h"] * 0.5
    tor_hd = tor["d"] * 0.5

    if has_skirt:
        sk_bot = float(B.get("skirtBottom") or (leg["top"] - (leg["top"] - leg["y"]) * 0.34))
        sc.add_rounded_box(
            W(0.0, 0.5 * (sk_bot + tor["y"] + 1.0), 0.0),
            (S_cm(tor_hw * 1.03), S_cm(0.5 * (tor["y"] + 1.0 - sk_bot)), S_cm(tor_hd * 1.04)),
            S_cm(0.55 if is_blocky else 1.75),
            c_bottom,
            rot=R,
            roughness=0.55,
        )
    else:
        pelvis_bot = tor["y"] - 5.5
        sc.add_rounded_box(
            W(0.0, 0.5 * (pelvis_bot + tor["y"] + 1.2), 0.0),
            (S_cm(tor_hw * 0.98), S_cm(0.5 * (tor["y"] + 1.2 - pelvis_bot)), S_cm(tor_hd * 0.98)),
            S_cm(0.48 if is_blocky else 1.55),
            c_bottom,
            rot=R,
            roughness=0.55,
        )

    if c_belt is not None:
        belt_y = float(B.get("waist") or (tor["y"] + 1.0))
        sc.add_rounded_box(
            W(0.0, belt_y, 0.0),
            (S_cm(tor_hw * 1.025), S_cm(1.4), S_cm(tor_hd * 1.025)),
            S_cm(0.35 if is_blocky else 0.8),
            c_belt,
            rot=R,
            roughness=0.40,
        )
        sc.add_rounded_box(
            W(0.0, belt_y, tor_hd + 0.35),
            (S_cm(2.3), S_cm(1.65), S_cm(0.42)),
            S_cm(0.25),
            c_buckle,
            rot=R,
            roughness=0.24,
        )

    # =========================================================================
    # 2. UNIFORM SHIRT TORSO, BREAST POCKETS & SHOULDER STRAPS
    # =========================================================================
    tor_cy = tor["y"] + tor_hh
    sc.add_rounded_box(
        W(0.0, tor_cy, 0.0),
        (S_cm(tor_hw), S_cm(tor_hh), S_cm(tor_hd)),
        S_cm(0.45 if is_blocky else 2.25),
        c_shirt,
        rot=R,
        roughness=0.52,
    )
    if not is_blocky:
        # Soft vinyl-toy rounded shoulder bridge in `bobo` mode (keeps front/sleeve badge planes untouched)
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(
                W(side * (tor_hw + 1.2), L["top"] - 2.4, 0.0),
                (S_cm(3.2), S_cm(2.4), S_cm(tor_hd * 0.72)),
                c_shirt,
                rot=R,
                roughness=0.52,
            )

    if B.get("pocket") and not casual_mode:
        pk = B["pocket"]
        flap_top_y = L["top"] - pk["top"]
        pk_bot_y = flap_top_y - pk["h"]
        pk_cy = 0.5 * (flap_top_y + pk_bot_y)
        flap_cy = flap_top_y - pk["flap"] * 0.5
        for side in (-1.0, 1.0):
            px = side * pk["x"]
            sc.add_rounded_box(
                W(px, pk_cy, tor_hd + 0.02),
                (S_cm(pk["w"] * 0.5), S_cm(pk["h"] * 0.5), S_cm(0.11)),
                S_cm(0.22),
                c_pocket,
                rot=R,
                roughness=0.56,
            )
            sc.add_rounded_box(
                W(px, flap_cy, tor_hd + 0.05),
                (S_cm(pk["w"] * 0.51), S_cm(pk["flap"] * 0.5), S_cm(0.12)),
                S_cm(0.20),
                c_shirt,
                rot=R,
                roughness=0.50,
            )

    # Venture & Leader tailored khaki shoulder straps (`strap`) supporting the shoulder epaulettes!
    if strap is not None:
        for side in (-1.0, 1.0):
            sc.add_rounded_box(
                W(side * strap["cx"], strap["boxY"], 0.0),
                (S_cm(strap["len"] * 0.5), S_cm(strap["boxT"] * 0.55), S_cm(strap["w"] * 0.5)),
                S_cm(0.22),
                c_pocket,
                rot=R,
                roughness=0.50,
            )

    # =========================================================================
    # 3. PROFICIENCY SASH ('專章帶': Left Shoulder +X -> Right Waist -X, UNDER Neckerchief!)
    # =========================================================================
    if sash_amt > 0.02 and sash_cfg is not None:
        # Tuck top & bottom centers inside shoulder/hip bounds so rotated corners never poke past torso silhouette
        p_top = v3(float(sash_cfg["cTop"]) - 0.8, L["top"] - 1.6, 0.0)
        p_bot = v3(-tor_hw + 4.4, float(sash_cfg["endY"]) + 2.6, 0.0)
        e_y = normalize(p_top - p_bot)
        e_z = v3(0.0, 0.0, 1.0)
        e_x = normalize(np.cross(e_y, e_z))
        R_sash_local = np.column_stack([e_x, e_y, e_z]).astype(np.float32)
        R_sash_world = R @ R_sash_local

        sash_mid_xy = 0.5 * (p_top + p_bot)
        sash_half_len = 0.5 * float(np.linalg.norm(p_top - p_bot)) * sash_amt
        green_hw = (float(sash_cfg["widthCm"]) * 0.5) * sash_amt
        red_hw = ((float(sash_cfg["widthCm"]) + 2.0 * float(sash_cfg["edgeCm"])) * 0.5) * sash_amt

        for z_sgn in (1.0, -1.0):
            sc.add_rounded_box(
                W(float(sash_mid_xy[0]), float(sash_mid_xy[1]), z_sgn * (tor_hd + 0.24)),
                (S_cm(red_hw), S_cm(sash_half_len), S_cm(0.11)),
                S_cm(0.16),
                COL["scout_red"],
                rot=R_sash_world,
                roughness=0.50,
            )
            sc.add_rounded_box(
                W(float(sash_mid_xy[0]), float(sash_mid_xy[1]), z_sgn * (tor_hd + 0.34)),
                (S_cm(green_hw), S_cm(sash_half_len * 0.995), S_cm(0.12)),
                S_cm(0.14),
                COL["scout_green"],
                rot=R_sash_world,
                roughness=0.48,
            )
        # Left-shoulder (+X) & right-hip (-X) wrap-around bridges
        sc.add_rounded_box(
            W(float(sash_cfg["cTop"]), L["top"] + 0.32, 0.0),
            (S_cm(red_hw * 0.85), S_cm(0.32), S_cm(tor_hd + 0.34)),
            S_cm(0.20),
            COL["scout_red"],
            rot=R,
            roughness=0.50,
        )
        sc.add_rounded_box(
            W(float(sash_cfg["cTop"]), L["top"] + 0.40, 0.0),
            (S_cm(green_hw * 0.85), S_cm(0.30), S_cm(tor_hd + 0.36)),
            S_cm(0.18),
            COL["scout_green"],
            rot=R,
            roughness=0.48,
        )
        sc.add_rounded_box(
            W(-tor_hw - 0.20, float(sash_cfg["endY"]) + 2.2, 0.0),
            (S_cm(0.32), S_cm(red_hw * 0.78), S_cm(tor_hd + 0.34)),
            S_cm(0.20),
            COL["scout_red"],
            rot=R,
            roughness=0.50,
        )
        sc.add_rounded_box(
            W(-tor_hw - 0.30, float(sash_cfg["endY"]) + 2.2, 0.0),
            (S_cm(0.30), S_cm(green_hw * 0.78), S_cm(tor_hd + 0.36)),
            S_cm(0.18),
            COL["scout_green"],
            rot=R,
            roughness=0.48,
        )

    # =========================================================================
    # 4. NECKERCHIEF ('領巾') & WOGGLE ('領巾圈') — Draped OVER Collar & Sash!
    # =========================================================================
    nk = B["necker"]
    if not casual_mode:
        collar_y = L["top"] + 0.55
        wog_y = L["top"] - float(nk["wogDrop"])
        wog_z = tor_hd + 1.15
        tip_y = wog_y - float(nk["tailLen"]) * 0.48

        for side in (-1.0, 1.0):
            if c_neck_trim is not None:
                sc.add_capsule(W(side * 6.6, collar_y, 1.8), W(0.0, wog_y - 0.3, wog_z - 0.14), S_cm(1.62), c_neck_trim, roughness=0.52)
            sc.add_capsule(W(side * 6.4, collar_y + 0.15, 1.9), W(0.0, wog_y, wog_z), S_cm(1.35), c_necker, roughness=0.50)

        # Back triangular neckerchief bib
        if c_neck_trim is not None:
            sc.add_rounded_box(
                W(0.0, L["top"] - float(nk["backH"]) * 0.45, -tor_hd - 0.38),
                (S_cm(float(nk["backW"]) * 0.28), S_cm(float(nk["backH"]) * 0.44), S_cm(0.30)),
                S_cm(0.42),
                c_neck_trim,
                rot=R,
                roughness=0.52,
            )
        sc.add_rounded_box(
            W(0.0, L["top"] - float(nk["backH"]) * 0.43, -tor_hd - 0.48),
            (S_cm(float(nk["backW"]) * 0.24), S_cm(float(nk["backH"]) * 0.38), S_cm(0.32)),
            S_cm(0.38),
            c_necker,
            rot=R,
            roughness=0.50,
        )
        for side in (-1.0, 1.0):
            sc.add_capsule(W(side * 0.35, wog_y - 0.8, wog_z - 0.05), W(side * 1.4, tip_y, tor_hd + 0.92), S_cm(0.92), c_necker, roughness=0.50)
        sc.add_ellipsoid(W(0.0, wog_y, wog_z + 0.25), (S_cm(1.70), S_cm(1.30), S_cm(1.40)), c_woggle, rot=R, roughness=0.28)

    # =========================================================================
    # 5. LEFT (+X) & RIGHT (-X) ARMS (Exact SCOUT3D `B.sleeve` + Rigid Badge Frame!)
    # =========================================================================
    slv = B["sleeve"]
    u_arm = B["upperArm"]
    l_arm = B["lowerArm"]
    hand = B["hand"]
    head = B["head"]
    sleeve_len = float(slv["len"])
    forearm_len = float(l_arm["h"])

    # --- Wearer's LEFT Arm (+X) ---
    l_pivot = v3(+float(L["armX"]), float(L["shoulderY"]), 0.0)
    wave_u = float(max(0.0, min(1.0, wave)))
    wave_osc = math.sin(t_sec * 10.0) * 14.0 * wave_u
    R_upper_l = rot_z(112.0 * wave_u + wave_osc * 0.4) @ rot_x(-10.0 * wave_u)
    l_elbow = l_pivot + (R_upper_l @ v3(0.0, -float(u_arm["h"]), 0.0))
    l_sleeve_mid = l_pivot + (R_upper_l @ v3(0.0, -sleeve_len * 0.5 + 1.0, 0.0))

    slv_hd = slv["d"] * 0.50
    slv_bevel = 0.45 if is_blocky else 1.35

    # 上臂本體（皮膚／機械外殼），短袖再疊喺上面 → 舉手／揮手時手臂唔會斷開
    sc.add_capsule(WV(l_pivot), WV(l_elbow), S_cm(u_arm["w"] * 0.44), c_limb, roughness=0.50)
    sc.add_rounded_box(
        WV(l_sleeve_mid),
        (S_cm(slv["w"] * 0.5), S_cm(sleeve_len * 0.5), S_cm(slv_hd)),
        S_cm(slv_bevel),
        c_shirt,
        rot=R @ R_upper_l,
        roughness=0.52,
    )
    R_fore_l = R_upper_l @ rot_z(72.0 * wave_u + wave_osc)
    l_wrist = l_elbow + (R_fore_l @ v3(0.0, -forearm_len, 0.0))
    if is_blocky:
        sc.add_rounded_box(
            WV(0.5 * (l_elbow + l_wrist)),
            (S_cm(l_arm["w"] * 0.5), S_cm(forearm_len * 0.52), S_cm(l_arm["d"] * 0.5)),
            S_cm(0.4),
            c_limb,
            rot=R @ R_fore_l,
            roughness=0.50,
        )
        sc.add_rounded_box(
            WV(l_wrist + (R_fore_l @ v3(0.0, -hand["h"] * 0.38, 0.0))),
            (S_cm(hand["w"] * 0.5), S_cm(hand["h"] * 0.45), S_cm(hand["d"] * 0.5)),
            S_cm(0.4),
            c_limb,
            rot=R @ R_fore_l,
            roughness=0.48,
        )
    else:
        sc.add_capsule(WV(l_elbow), WV(l_wrist), S_cm(l_arm["w"] * 0.48), c_limb, roughness=0.50)
        sc.add_sphere(WV(l_wrist + (R_fore_l @ v3(0.0, -hand["h"] * 0.30, 0.0))), S_cm(hand["w"] * 0.56), c_limb, roughness=0.48)

    # --- Wearer's RIGHT Arm (-X): relaxed at 0.0 -> crisp 3-finger HK Scout Salute at 1.0 ---
    r_pivot = v3(-float(L["armX"]), float(L["shoulderY"]), 0.0)
    sal_u = float(max(0.0, min(1.0, salute)))
    # Lift right elbow outward (-X) and slightly forward (+Z) so all right-sleeve badges stay readable
    R_upper_r = rot_x(-24.0 * sal_u) @ rot_z(-40.0 * sal_u)
    r_elbow = r_pivot + (R_upper_r @ v3(0.0, -float(u_arm["h"]), 0.0))
    r_sleeve_mid = r_pivot + (R_upper_r @ v3(0.0, -sleeve_len * 0.5 + 1.0, 0.0))

    # 右上臂本體（皮膚／機械外殼），短袖疊面
    sc.add_capsule(WV(r_pivot), WV(r_elbow), S_cm(u_arm["w"] * 0.44), c_limb, roughness=0.50)
    sc.add_rounded_box(
        WV(r_sleeve_mid),
        (S_cm(slv["w"] * 0.5), S_cm(sleeve_len * 0.5), S_cm(slv_hd)),
        S_cm(slv_bevel),
        c_shirt,
        rot=R @ R_upper_r,
        roughness=0.52,
    )

    r_wrist_rest = r_elbow + v3(0.0, -forearm_len, 0.0)
    r_wrist_salute = v3(-head["w"] * 0.5 - 3.2, head["y"] + head["h"] * 0.44, head["d"] * 0.5 + 2.2)
    r_wrist = r_wrist_rest * (1.0 - sal_u) + r_wrist_salute * sal_u

    if is_blocky and sal_u < 0.05:
        sc.add_rounded_box(
            WV(0.5 * (r_elbow + r_wrist)),
            (S_cm(l_arm["w"] * 0.5), S_cm(forearm_len * 0.52), S_cm(l_arm["d"] * 0.5)),
            S_cm(0.4),
            c_limb,
            rot=R,
            roughness=0.50,
        )
        sc.add_rounded_box(
            WV(r_wrist + v3(0.0, -hand["h"] * 0.38, 0.0)),
            (S_cm(hand["w"] * 0.5), S_cm(hand["h"] * 0.45), S_cm(hand["d"] * 0.5)),
            S_cm(0.4),
            c_limb,
            rot=R,
            roughness=0.48,
        )
    else:
        sc.add_capsule(WV(r_elbow), WV(r_wrist), S_cm(l_arm["w"] * 0.48), c_limb, roughness=0.50)
        sc.add_sphere(WV(r_wrist), S_cm(hand["w"] * 0.52), c_limb, roughness=0.48)

    if sal_u > 0.5:
        for fx_cm in (-1.30, 0.0, 1.30):
            sc.add_capsule(
                WV(r_wrist + v3(fx_cm, 1.2, 0.2)),
                WV(r_wrist + v3(fx_cm * 0.88 + 0.8, 6.2, 0.2)),
                S_cm(0.70),
                c_limb,
                roughness=0.46,
            )
        sc.add_capsule(WV(r_wrist + v3(1.6, 0.4, 1.5)), WV(r_wrist + v3(-0.8, 1.5, 1.7)), S_cm(0.70), c_limb, roughness=0.46)

    # =========================================================================
    # 6. NECK, HEAD, HAIR, OPTIONAL SECTION HEADWEAR & EXPRESSIVE FACE
    # =========================================================================
    neck = B["neck"]
    sc.add_capsule(W(0.0, neck["y"] - 0.5, 0.0), W(0.0, head["y"] + 2.0, head["z"] * 0.5), S_cm(neck["w"] * 0.42), c_limb, roughness=0.50)

    head_cy = head["y"] + head["h"] * 0.5
    head_hw = head["w"] * 0.5
    head_hh = head["h"] * 0.5
    head_hd = head["d"] * 0.5
    hz = head["z"]

    if is_robot:
        c_shell = hex_rgb01("#EEF3FA")
        c_visor = hex_rgb01("#142236")
        c_led = hex_rgb01("#38EEFF")
        c_ear = hex_rgb01("#4FA8E8")
        sc.add_rounded_box(
            W(0.0, head_cy, hz),
            (S_cm(head_hw * 1.06), S_cm(head_hh * 0.96), S_cm(head_hd * 1.02)),
            S_cm(2.8 if not is_blocky else 1.1),
            c_shell,
            rot=R,
            roughness=0.26,
        )
        visor_z = hz + head_hd * 0.86
        sc.add_rounded_box(
            W(0.0, head_cy - 0.2, visor_z),
            (S_cm(head_hw * 0.84), S_cm(head_hh * 0.58), S_cm(1.6)),
            S_cm(1.5),
            c_visor,
            rot=R,
            roughness=0.14,
        )
        for side in (-1.0, 1.0):
            sc.add_cylinder(
                W(side * (head_hw * 1.02), head_cy - 0.3, hz),
                W(side * (head_hw * 1.18), head_cy - 0.3, hz),
                S_cm(2.5),
                c_ear,
                roughness=0.25,
            )
        ant_sway = math.sin(t_sec * 7.0) * 1.4
        sc.add_capsule(
            W(0.0, head_cy + head_hh * 0.92, hz),
            W(ant_sway, head_cy + head_hh * 1.42, hz),
            S_cm(0.65),
            hex_rgb01("#9AA9BC"),
            roughness=0.30,
        )
        sc.add_sphere(
            W(ant_sway, head_cy + head_hh * 1.50, hz),
            S_cm(1.85),
            c_led,
            roughness=0.10,
            emissive=(0.22, 0.72, 0.85),
        )
        led_z = visor_z + 1.55
        eye_x = head_hw * 0.36
        for side in (-1.0, 1.0):
            ex = side * eye_x
            if expression == "nervous":
                sc.add_capsule(W(ex - 1.2, head_cy + 1.2, led_z), W(ex + 1.2, head_cy - 1.0, led_z), S_cm(0.50), hex_rgb01("#FF857A"), emissive=(0.75, 0.22, 0.18))
                sc.add_capsule(W(ex - 1.2, head_cy - 1.0, led_z), W(ex + 1.2, head_cy + 1.2, led_z), S_cm(0.50), hex_rgb01("#FF857A"), emissive=(0.75, 0.22, 0.18))
            else:
                sc.add_capsule(W(ex - 1.3, head_cy + 0.1, led_z), W(ex, head_cy + 1.4, led_z), S_cm(0.58), c_led, emissive=(0.20, 0.75, 0.88))
                sc.add_capsule(W(ex, head_cy + 1.4, led_z), W(ex + 1.3, head_cy + 0.1, led_z), S_cm(0.58), c_led, emissive=(0.20, 0.75, 0.88))
        if expression == "nervous":
            sc.add_capsule(W(-2.0, head_cy - 3.6, led_z), W(2.0, head_cy - 3.6, led_z), S_cm(0.45), hex_rgb01("#FF857A"), emissive=(0.7, 0.2, 0.2))
        else:
            sc.add_capsule(W(-2.1, head_cy - 3.0, led_z), W(0.0, head_cy - 4.0, led_z), S_cm(0.48), c_led, emissive=(0.20, 0.75, 0.88))
            sc.add_capsule(W(0.0, head_cy - 4.0, led_z), W(2.1, head_cy - 3.0, led_z), S_cm(0.48), c_led, emissive=(0.20, 0.75, 0.88))
    else:
        if is_blocky:
            sc.add_rounded_box(
                W(0.0, head_cy, hz),
                (S_cm(head_hw), S_cm(head_hh), S_cm(head_hd)),
                S_cm(0.90),
                COL["skin"],
                rot=R,
                roughness=0.48,
            )
            sc.add_rounded_box(
                W(0.0, head_cy + head_hh * 0.78, hz - 0.4),
                (S_cm(head_hw + 0.65), S_cm(head_hh * 0.28), S_cm(head_hd + 0.55)),
                S_cm(0.75),
                COL["hair_dark"],
                rot=R,
                roughness=0.45,
            )
            sc.add_rounded_box(
                W(0.0, head_cy + 0.5, hz - head_hd * 0.72),
                (S_cm(head_hw + 0.45), S_cm(head_hh * 0.74), S_cm(head_hd * 0.35)),
                S_cm(0.75),
                COL["hair_dark"],
                rot=R,
                roughness=0.45,
            )
            face_z = hz + head_hd + 0.25
            ear_x = head_hw + 0.45
        else:
            sc.add_ellipsoid(
                W(0.0, head_cy, hz),
                (S_cm(head_hw * 1.08), S_cm(head_hh * 1.04), S_cm(head_hd * 1.06)),
                COL["skin"],
                rot=R,
                roughness=0.46,
            )
            sc.add_ellipsoid(
                W(0.0, head_cy + head_hh * (0.12 if wear_hat else 0.22), hz - 1.5),
                (S_cm(head_hw * 1.12), S_cm(head_hh * (0.88 if wear_hat else 1.02)), S_cm(head_hd * 1.04)),
                COL["hair_dark"],
                rot=R,
                roughness=0.44,
            )
            if not wear_hat:
                for bx_f, by_f, bz_f, br_f in [
                    (-0.48, 0.78, 0.56, 0.36),
                    (0.0, 0.84, 0.62, 0.39),
                    (0.48, 0.78, 0.56, 0.36),
                    (-0.80, 0.58, 0.32, 0.30),
                    (0.80, 0.58, 0.32, 0.30),
                ]:
                    sc.add_sphere(
                        W(bx_f * head_hw, head_cy + by_f * head_hh, hz + bz_f * head_hd),
                        S_cm(br_f * head_hw),
                        COL["hair_dark"],
                        roughness=0.42,
                    )
            face_z = hz + head_hd * 1.06
            ear_x = head_hw * 1.08

        for side in (-1.0, 1.0):
            sc.add_ellipsoid(W(side * ear_x, head_cy - 0.6, hz + 0.3), (S_cm(1.8), S_cm(2.6), S_cm(1.7)), COL["skin"], rot=R)
            if is_girl:
                sc.add_sphere(W(side * (ear_x + 1.4), head_cy + 0.8, hz - 2.2), S_cm(2.7), COL["hair_dark"], roughness=0.42)
                sc.add_capsule(
                    W(side * (ear_x + 1.7), head_cy + 0.3, hz - 2.4),
                    W(side * (ear_x + 3.2), head_cy - 6.6, hz - 1.9),
                    S_cm(2.2),
                    COL["hair_dark"],
                    roughness=0.42,
                )

        if wear_hat:
            _draw_headwear(sc, W, WV, WN, R, S_cm, head, variant, is_blocky)

        eye_x = head_hw * 0.38
        eye_y = head_cy + 0.2
        for side in (-1.0, 1.0):
            ex = side * eye_x
            sc.add_sphere(W(ex, eye_y, face_z - 0.3), S_cm(1.30), COL["eye_dark"], roughness=0.12)
            sc.add_sphere(W(ex - 0.38, eye_y + 0.45, face_z + 0.78), S_cm(0.44), COL["white"], roughness=0.05, emissive=(0.4, 0.4, 0.4))
            if expression == "nervous":
                sc.add_capsule(W(ex - side * 1.3, head_cy + 3.2, face_z - 0.5), W(ex + side * 1.3, head_cy + 2.2, face_z - 0.5), S_cm(0.46), COL["hair_dark"])
            else:
                sc.add_capsule(W(ex - 1.3, head_cy + 3.0, face_z - 0.5), W(ex + 1.3, head_cy + 3.2, face_z - 0.5), S_cm(0.46), COL["hair_dark"])

        sc.add_sphere(W(0.0, head_cy - 1.35, face_z + 0.65), S_cm(1.0), COL["skin"], roughness=0.42)
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(W(side * (head_hw * 0.58), head_cy - 1.9, face_z - 1.25), (S_cm(1.55), S_cm(0.95), S_cm(0.8)), COL["blush"], rot=R)

        if expression == "nervous":
            sc.add_capsule(W(-2.0, head_cy - 4.1, face_z - 0.3), W(0.0, head_cy - 3.5, face_z), S_cm(0.46), COL["maroon"])
            sc.add_capsule(W(0.0, head_cy - 3.5, face_z), W(2.0, head_cy - 4.1, face_z - 0.3), S_cm(0.46), COL["maroon"])
            sc.add_ellipsoid(W(head_hw * 0.78, head_cy + 2.3, face_z - 1.4), (S_cm(0.82), S_cm(1.40), S_cm(0.82)), hex_rgb01("#5EC8F8"), rot=R, roughness=0.15)
        elif expression == "surprised":
            sc.add_sphere(W(0.0, head_cy - 3.9, face_z), S_cm(1.15), COL["maroon"])
        else:
            sc.add_capsule(W(-2.4, head_cy - 3.3, face_z - 0.4), W(-0.85, head_cy - 4.2, face_z), S_cm(0.50), COL["maroon"])
            sc.add_capsule(W(-0.85, head_cy - 4.2, face_z), W(0.85, head_cy - 4.2, face_z), S_cm(0.50), COL["maroon"])
            sc.add_capsule(W(0.85, head_cy - 4.2, face_z), W(2.4, head_cy - 3.3, face_z - 0.4), S_cm(0.50), COL["maroon"])

    # =========================================================================
    # 7. AUTHORITATIVE SCOUT3D PROGRAMMATIC BADGE RENDERING (RGBA PNG PATCHES!)
    # =========================================================================
    if badge_mode == "wrong":
        for wb in get_wrong_messy_badges_local():
            tex = _get_badge_rgba(wb["file"])
            if tex is None:
                continue
            p_w = base_pos + (R @ (wb["pos"] * scale))
            sc.add_textured_patch_3d(
                p_w,
                WN(wb["nrm"]),
                WN(wb["u_right"]),
                WN(wb["v_up"]),
                wb["w"] * scale,
                wb["h"] * scale,
                tex,
                lift=0.008 * scale,
            )
        return

    if badge_mode not in ("correct", "animated"):
        return

    hi_set = set(highlight_slots or ())

    for p in badges:
        s_key = str(p.get("key") or p.get("id") or "badge")
        s_id = str(p.get("id") or s_key)
        rel_file = str(p.get("art") or "")
        dyn_meta = p.get("dyn") if isinstance(p.get("dyn"), dict) else None
        if not rel_file and not dyn_meta:
            continue

        is_sash_badge = bool(p.get("onSash"))
        if is_sash_badge and sash_amt < 0.55:
            continue

        prog = 1.0 if badge_mode == "correct" else _slot_progress(s_key, s_id, badge_progress)
        if prog <= 0.01:
            continue

        patch_shape = "circle" if p.get("shape") == "circle" else "rect"
        tex = _get_badge_rgba(rel_file, dyn=dyn_meta, shape=patch_shape, label_zh=str(p.get("zh") or ""))
        if tex is None:
            continue

        mount = p.get("mount", "torso")
        facing = p.get("facing", "front")
        rot_z_rad = float(p.get("rotZ", 0.0))

        if mount == "r":
            alp = p["armLocalPos"]
            # Push outward slightly (`-slv.w/2 - 0.16`) so patch sits cleanly on top of the right sleeve box
            local_off = v3(-slv["w"] * 0.5 - 0.16, float(alp[1]), float(alp[2]))
            target_cm = r_pivot + (R_upper_r @ local_off)
            n_loc = R_upper_r @ v3(-1.0, 0.0, 0.0)
            u_loc = R_upper_r @ v3(*p["armArtRight"])
            v_loc = R_upper_r @ v3(0.0, +1.0, 0.0)
        elif mount == "l":
            alp = p["armLocalPos"]
            local_off = v3(+slv["w"] * 0.5 + 0.16, float(alp[1]), float(alp[2]))
            target_cm = l_pivot + (R_upper_l @ local_off)
            n_loc = R_upper_l @ v3(+1.0, 0.0, 0.0)
            u_loc = R_upper_l @ v3(*p["armArtRight"])
            v_loc = R_upper_l @ v3(0.0, +1.0, 0.0)
        elif facing == "up":
            # Shoulder Epaulettes (`venture_epaulette.png` or `leader/epaulette_sl.png`)
            ep_y = (strap["boxY"] + strap["boxT"] * 0.6 + 0.12) if strap else (L["top"] + 0.35)
            target_cm = v3(float(p["x"]), ep_y, float(p["z"]))
            n_loc = v3(0.0, +1.0, 0.0)
            if rel_file == "venture_epaulette.png":
                # Horizontal PNG (w=9, h=3.8): left = square V-wreath (outer shoulder), right = button (collar)
                pw_cm, ph_cm = float(p["w"]), float(p["h"])
                if p["x"] < 0:
                    u_loc = v3(+1.0, 0.0, 0.0)
                    v_loc = v3(0.0, 0.0, -1.0)
                else:
                    u_loc = v3(-1.0, 0.0, 0.0)
                    v_loc = v3(0.0, 0.0, +1.0)
            else:
                # Vertical PNG (`leader/epaulette_sl.png`, image is tall: top = pointed collar end!)
                # In `Badges.jsx`, plane is `[p.h, p.w]` rotated 90 deg so `p.w` (4.6 cm) runs along shoulder X!
                pw_cm, ph_cm = float(p["h"]), float(p["w"])
                if p["x"] < 0:
                    v_loc = v3(+1.0, 0.0, 0.0)
                    u_loc = v3(0.0, 0.0, +1.0)
                else:
                    v_loc = v3(-1.0, 0.0, 0.0)
                    u_loc = v3(0.0, 0.0, -1.0)
        elif facing == "back":
            target_cm = v3(float(p["x"]), float(p["y"]), -tor_hd - 0.68)
            n_loc = v3(0.0, 0.0, -1.0)
            cs, sn = math.cos(rot_z_rad), math.sin(rot_z_rad)
            u_loc = v3(-cs, sn, 0.0)
            v_loc = v3(sn, cs, 0.0)
        else:
            z_cm = (tor_hd + 0.54) if is_sash_badge else (tor_hd + 0.24)
            target_cm = v3(float(p["x"]), float(p["y"]), z_cm)
            n_loc = v3(0.0, 0.0, +1.0)
            cs, sn = math.cos(rot_z_rad), math.sin(rot_z_rad)
            u_loc = v3(cs, sn, 0.0)
            v_loc = v3(-sn, cs, 0.0)

        if facing != "up":
            pw_cm, ph_cm = float(p["w"]), float(p["h"])

        fly_t = min(1.0, prog)
        ease = 1.0 - (1.0 - fly_t) ** 3
        if fly_t < 0.995:
            side_sgn = 1.0 if target_cm[0] >= 0 else -1.0
            start_cm = target_cm + v3(46.0 * side_sgn, 24.0, 42.0)
            cur_cm = start_cm * (1.0 - ease) + target_cm * ease
            pop_scale = 1.0 + 0.25 * math.sin(fly_t * math.pi)
            glow_amt = 0.60 * (1.0 - fly_t)
        else:
            cur_cm = target_cm
            pop_scale = 1.0
            glow_amt = 0.38 if (s_key in hi_set or s_id in hi_set) else 0.0

        patch_shape = "circle" if p.get("shape") == "circle" else "rect"
        sc.add_textured_patch_3d(
            WV(cur_cm),
            WN(n_loc),
            WN(u_loc),
            WN(v_loc),
            S_cm(pw_cm * pop_scale),
            S_cm(ph_cm * pop_scale),
            tex,
            shape=patch_shape,
            lift=S_cm(0.08),
            glow=glow_amt,
        )


def draw_mom_figure(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    mood: str = "dizzy",  # "dizzy" | "happy"
    t_sec: float = 0.0,
) -> None:
    """Adorable '波波圓滑 3D' Mom character (cozy coral sweater, high hair bun, zero face occlusion)."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.05), strength=0.50)

    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * 0.18, 0.09, 0.05), (S(0.11), S(0.08), S(0.16)), COL["maroon"], rot=R)
        sc.add_capsule(W(side * 0.18, 0.16, 0.0), W(side * 0.18, 0.78, 0.0), S(0.095), COL["skin"])

    sc.add_cylinder(W(0.0, 0.72, 0.0), W(0.0, 1.12, 0.0), S(0.36), COL["mom_skirt"], roughness=0.55)
    sc.add_rounded_box(W(0.0, 1.48, 0.0), (S(0.34), S(0.36), S(0.25)), S(0.17), COL["mom_sweater"], rot=R, roughness=0.52)
    sc.add_ellipsoid(W(0.0, 1.82, 0.08), (S(0.20), S(0.06), S(0.16)), COL["white"], rot=R)

    bob_a = math.sin(t_sec * 6.0) * 0.05
    if mood == "dizzy":
        sc.add_capsule(W(-0.40, 1.74, 0.0), W(-0.52, 2.02 + bob_a, 0.18), S(0.105), COL["mom_sweater"])
        sc.add_sphere(W(-0.52, 2.05 + bob_a, 0.20), S(0.095), COL["skin"])
        sc.add_capsule(W(0.40, 1.74, 0.0), W(0.50, 1.42, 0.24), S(0.105), COL["mom_sweater"])
        sc.add_sphere(W(0.50, 1.38, 0.26), S(0.095), COL["skin"])
    else:
        sc.add_capsule(W(-0.40, 1.74, 0.0), W(-0.34, 1.44 + bob_a, 0.32), S(0.105), COL["mom_sweater"])
        sc.add_sphere(W(-0.32, 1.42 + bob_a, 0.35), S(0.095), COL["skin"])
        sc.add_capsule(W(0.40, 1.74, 0.0), W(0.34, 1.46 - bob_a, 0.32), S(0.105), COL["mom_sweater"])
        sc.add_sphere(W(0.32, 1.44 - bob_a, 0.35), S(0.095), COL["skin"])

    sc.add_capsule(W(0.0, 1.82, 0.0), W(0.0, 1.98, 0.0), S(0.115), COL["skin"])
    hy = 2.26
    sc.add_ellipsoid(W(0.0, hy, 0.02), (S(0.37), S(0.35), S(0.35)), COL["skin"], rot=R, roughness=0.46)
    sc.add_ellipsoid(W(0.0, hy + 0.08, -0.06), (S(0.39), S(0.35), S(0.36)), COL["hair_mom"], rot=R, roughness=0.44)
    sc.add_sphere(W(0.0, hy + 0.44, -0.06), S(0.17), COL["hair_mom"], roughness=0.42)
    for bx_h in (-0.16, 0.0, 0.16):
        sc.add_sphere(W(bx_h, hy + 0.27, 0.19), S(0.13), COL["hair_mom"], roughness=0.42)

    fz = 0.355
    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * 0.37, hy - 0.02, 0.02), (S(0.065), S(0.09), S(0.06)), COL["skin"], rot=R)
        ex = side * 0.13
        sc.add_sphere(W(ex, hy + 0.01, fz - 0.01), S(0.044), COL["eye_dark"], roughness=0.12)
        sc.add_sphere(W(ex - 0.012, hy + 0.015, fz + 0.026), S(0.014), COL["white"], roughness=0.05, emissive=(0.4, 0.4, 0.4))
        sc.add_ellipsoid(W(side * 0.20, hy - 0.065, fz - 0.045), (S(0.055), S(0.034), S(0.03)), COL["blush"], rot=R)

    sc.add_sphere(W(0.0, hy - 0.04, fz + 0.025), S(0.034), COL["skin"])
    if mood == "dizzy":
        sc.add_sphere(W(0.0, hy - 0.135, fz), S(0.036), COL["maroon"])
        for k_i in range(3):
            ang = t_sec * 4.5 + k_i * (2.0 * math.pi / 3.0)
            sc.add_sphere(
                W(0.32 * math.cos(ang), hy + 0.56 + 0.03 * math.sin(ang * 2), 0.32 * math.sin(ang)),
                S(0.052),
                COL["gold"],
                roughness=0.2,
                emissive=(0.35, 0.28, 0.05),
            )
    else:
        sc.add_capsule(W(-0.08, hy - 0.115, fz - 0.015), W(0.0, hy - 0.148, fz), S(0.018), COL["maroon"])
        sc.add_capsule(W(0.0, hy - 0.148, fz), W(0.08, hy - 0.115, fz - 0.015), S(0.018), COL["maroon"])


def draw_leader_figure(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    mood: str = "scold",  # "scold" | "praise"
    t_sec: float = 0.0,
    show_sign: bool = True,  # False = plain story-scene leader (no floating X / check sign)
) -> None:
    """Adult HK Scout Leader wearing the exact SCOUT3D `leader` uniform & RGBA badges,
    plus 3D Red-X warning sign (`mood='scold'`) or Salute + Green Check (`mood='praise'`).
    """
    eff_scale = scale * 0.94
    expr = "nervous" if mood == "scold" else "proud"
    draw_scout_figure(
        sc,
        base_pos,
        yaw_deg=yaw_deg,
        scale=eff_scale,
        style_mode="bobo",
        expression=expr,
        salute=0.0 if mood == "scold" else 1.0,
        badge_mode="correct",
        section="leader",
        gender="M",
        hat=True,
        t_sec=t_sec,
    )

    if not show_sign:
        return

    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    bob = math.sin(t_sec * 5.0) * 0.04
    sx_c, sy_c, sz_c = -0.34, 2.94 + bob, 0.34
    if mood == "scold":
        sc.add_cylinder(
            W(sx_c, sy_c, sz_c - 0.04),
            W(sx_c, sy_c, sz_c + 0.04),
            S(0.25),
            COL["warn_red"],
            roughness=0.30,
            emissive=(0.25, 0.02, 0.02),
        )
        sc.add_capsule(W(sx_c - 0.11, sy_c - 0.11, sz_c + 0.06), W(sx_c + 0.11, sy_c + 0.11, sz_c + 0.06), S(0.040), COL["white"])
        sc.add_capsule(W(sx_c - 0.11, sy_c + 0.11, sz_c + 0.06), W(sx_c + 0.11, sy_c - 0.11, sz_c + 0.06), S(0.040), COL["white"])
    else:
        sc.add_cylinder(
            W(sx_c, sy_c, sz_c - 0.04),
            W(sx_c, sy_c, sz_c + 0.04),
            S(0.26),
            COL["ok_green"],
            roughness=0.28,
            emissive=(0.04, 0.25, 0.10),
        )
        sc.add_capsule(W(sx_c - 0.11, sy_c - 0.01, sz_c + 0.06), W(sx_c - 0.02, sy_c - 0.10, sz_c + 0.06), S(0.040), COL["white"])
        sc.add_capsule(W(sx_c - 0.02, sy_c - 0.10, sz_c + 0.06), W(sx_c + 0.13, sy_c + 0.10, sz_c + 0.06), S(0.040), COL["white"])


def draw_handbook_stack(sc: Scene3D, base_pos: np.ndarray, yaw_deg: float = 0.0, scale: float = 1.0) -> None:
    """Giant stack of 3 thick uniform manuals (zero baked text)."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.00), strength=0.48)

    books = [
        (0.11, COL["book_a"], 4.0),
        (0.33, COL["book_b"], -7.0),
        (0.55, COL["book_c"], 6.0),
    ]
    for by, col, twist in books:
        rb = R @ rot_y(twist)
        sc.add_rounded_box(W(0.0, by, 0.0), (S(0.38), S(0.105), S(0.28)), S(0.025), col, rot=rb, roughness=0.48)
        sc.add_rounded_box(W(0.02, by, 0.02), (S(0.35), S(0.082), S(0.26)), S(0.015), COL["pages"], rot=rb, roughness=0.62)


def draw_camp_tent(sc: Scene3D, base_pos: np.ndarray, yaw_deg: float = 0.0, scale: float = 1.0) -> None:
    """3D Scout A-Frame Camp Tent prop (two pitched panels + ridge pole + door flap)."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.00), strength=0.24)

    # Ground sheet
    sc.add_rounded_box(W(0.0, 0.02, 0.0), (S(0.62), S(0.025), S(0.66)), S(0.02), COL["tent_tan"], rot=R, roughness=0.72)

    # Two pitched roof panels meeting at the ridge (y ~ 0.94)
    for side in (-1.0, 1.0):
        sc.add_rounded_box(
            W(side * 0.37, 0.50, 0.0),
            (S(0.58), S(0.048), S(0.66)),
            S(0.022),
            COL["tent_green"],
            rot=R @ rot_z(-50.0 * side),
            roughness=0.66,
        )
    # Ridge pole
    sc.add_capsule(W(0.0, 0.955, -0.68), W(0.0, 0.955, 0.68), S(0.034), COL["khaki_dark"], roughness=0.55)

    # Door flap on the front panel (slightly ajar) + two door poles
    sc.add_rounded_box(W(-0.10, 0.44, 0.60), (S(0.19), S(0.40), S(0.020)), S(0.018), COL["tent_tan"], rot=R @ rot_z(9.0), roughness=0.72)
    for side in (-1.0, 1.0):
        sc.add_capsule(W(side * 0.34, 0.0, 0.62), W(side * 0.34, 0.70, 0.62), S(0.028), COL["khaki_dark"], roughness=0.55)

    # Guy lines
    for side in (-1.0, 1.0):
        sc.add_capsule(W(side * 0.74, 0.06, 0.40), W(side * 0.96, 0.0, 0.78), S(0.012), hex_rgb01("#E8E2D2"), roughness=0.80)


def draw_campfire(
    sc: Scene3D,
    base_pos: np.ndarray,
    scale: float = 1.0,
    t_sec: float = 0.0,
) -> None:
    """3D Scout campfire prop: stone ring, crossed logs, live flickering flames (no baked text)."""
    base = base_pos
    S = lambda d: d * scale
    W = lambda lx, ly, lz: base + v3(lx * scale, ly * scale, lz * scale)
    sc.add_floor_shadow(float(base[0]), float(base[2]), S(1.05), strength=0.30)

    # Stone ring
    for k in range(9):
        ang = (2.0 * math.pi / 9.0) * k
        sc.add_sphere(
            W(math.cos(ang) * 0.72, S(0.07), math.sin(ang) * 0.72),
            S(0.115),
            hex_rgb01("#8C8F96"),
            roughness=0.72,
        )

    # Crossed logs
    for ang_deg in (18.0, -34.0, 62.0):
        ra = rot_y(ang_deg)
        pa = W(0.0, 0.10, 0.0) + (ra @ v3(-0.34 * scale, 0.0, 0.0))
        pb = W(0.0, 0.10, 0.0) + (ra @ v3(0.34 * scale, 0.0, 0.0))
        sc.add_capsule(pa, pb, S(0.072), hex_rgb01("#6B4A2F"), roughness=0.78)

    # Ember bed
    sc.add_ellipsoid(W(0.0, 0.115, 0.0), (S(0.27), S(0.055), S(0.27)), hex_rgb01("#C4501B"), roughness=0.45, emissive=(0.62, 0.18, 0.02))

    # Flickering tapered flame tongues (stacked spheres, narrow at the tip)
    flick = 0.90 + 0.10 * math.sin(t_sec * 9.0) + 0.05 * math.sin(t_sec * 21.0 + 1.3)
    flame_layers = [
        ("#FF5A22", 0.150, 4, 0.20, 0.115, (0.95, 0.34, 0.03)),
        ("#FF9A2E", 0.105, 4, 0.27, 0.120, (1.00, 0.58, 0.10)),
        ("#FFD166", 0.062, 3, 0.33, 0.110, (1.00, 0.86, 0.36)),
    ]
    for col, r0, n_ball, y0, step, emi in flame_layers:
        for bi in range(n_ball):
            frac = bi / float(max(1, n_ball - 1))
            rad = r0 * (1.0 - 0.55 * frac)
            yy = (y0 + step * bi) * flick
            sway = math.sin(t_sec * 7.5 + bi * 0.9) * 0.020 * (1.0 + frac)
            sc.add_sphere(W(sway, S(yy), 0.0), S(rad), hex_rgb01(col), roughness=0.28, emissive=emi)

    # Sparks rising
    for k in range(5):
        ph = (t_sec * 0.55 + k * 0.21) % 1.0
        sx = math.sin(k * 2.1 + t_sec * 1.7) * 0.24
        sz = math.cos(k * 1.7 + t_sec * 1.3) * 0.24
        sc.add_sphere(
            W(sx, S(0.62 + 0.72 * ph), sz),
            S(0.030 * (1.0 - 0.45 * ph)),
            hex_rgb01("#FFCF6B"),
            roughness=0.15,
            emissive=(1.0, 0.72, 0.20),
        )


def draw_pine_tree(
    sc: Scene3D,
    base_pos: np.ndarray,
    scale: float = 1.0,
) -> None:
    """3D stylised conifer (5 slim flared tiers) for outdoor camp / forest scenes."""
    base = base_pos
    S = lambda d: d * scale
    W = lambda lx, ly, lz: base + v3(lx * scale, ly * scale, lz * scale)
    sc.add_floor_shadow(float(base[0]), float(base[2]), S(0.55), strength=0.20)
    sc.add_cylinder(W(0.0, 0.0, 0.0), W(0.0, 0.62, 0.0), S(0.080), hex_rgb01("#6A4A32"), roughness=0.80)
    tiers = [
        (0.58, 0.50, 0.30, "#1B5E37"),
        (0.84, 0.43, 0.28, "#20693E"),
        (1.08, 0.36, 0.25, "#257445"),
        (1.30, 0.28, 0.22, "#2B814C"),
        (1.50, 0.20, 0.19, "#339057"),
    ]
    for cy, rad, hh, col in tiers:
        sc.add_ellipsoid(W(0.0, cy, 0.0), (S(rad), S(hh), S(rad)), hex_rgb01(col), roughness=0.68)
    sc.add_sphere(W(0.0, 1.64, 0.0), S(0.115), hex_rgb01("#3AA063"), roughness=0.62)


# ═══════════════════════════════════════════════════════════════════════
# 動物角色（由零砌，唔係喺人頭上面貼耳仔）
# ═══════════════════════════════════════════════════════════════════════

ANIMAL_SPECIES: Dict[str, str] = {
    "cat": "貓", "sheep": "綿羊", "dog": "狗", "rabbit": "兔",
    "bear": "熊", "fox": "狐狸", "panda": "熊貓",
}

ANIMAL_FUR: Dict[str, str] = {
    "cat": "#F0A45C", "sheep": "#F7F1E3", "dog": "#C98B5A", "rabbit": "#F4F1EC",
    "bear": "#9A6A45", "fox": "#E8863F", "panda": "#F7F7F5",
}

ANIMAL_ACCENT: Dict[str, str] = {
    "cat": "#FFD9AE", "sheep": "#E7D9C3", "dog": "#F2D3AE", "rabbit": "#F7C9CE",
    "bear": "#D3A97C", "fox": "#FFF3E2", "panda": "#242424",
}

ANIMAL_LIMB: Dict[str, str] = {
    "panda": "#2A2A2A",
}


def _shade(rgb: RGBf, f: float) -> RGBf:
    return (max(0.0, min(1.0, rgb[0] * f)), max(0.0, min(1.0, rgb[1] * f)), max(0.0, min(1.0, rgb[2] * f)))


def _as_hex(value: Any, fallback: str) -> RGBf:
    txt = str(value or "").strip()
    if len(txt) in (6, 7) and txt.replace("#", "").isalnum():
        try:
            return hex_rgb01(txt if txt.startswith("#") else "#" + txt)
        except Exception:
            return hex_rgb01(fallback)
    return hex_rgb01(fallback)


def _draw_animal_head(
    sc: Scene3D,
    W_base,
    S,
    R: np.ndarray,
    sp: str,
    c_fur: RGBf,
    c_soft: RGBf,
    ox: float = 0.0,
    oy: float = 0.0,
    oz: float = 0.0,
    dy: float = 0.0,
    expression: str = "happy",
    t_sec: float = 0.0,
    head_scale: float = 0.80,
) -> None:
    """Shared species head (muzzle, nose, eyes, ears, whiskers, markings).

    Coordinates are the same as the biped rig, offset by (ox, oy+dy, oz) and scaled
    about the head centre so the chibi head still leaves room for the body.
    """
    k = float(head_scale)
    centre_y = 1.68

    def W(x: float, y: float, z: float) -> np.ndarray:
        return W_base(x * k + ox, (y - centre_y) * k + centre_y + oy + dy, z * k + oz)

    head_cy = 1.68
    head_rx, head_ry, head_rz = 0.44, 0.40, 0.40
    if sp == "bear":
        head_rx, head_ry, head_rz = 0.47, 0.41, 0.42
    elif sp == "rabbit":
        head_rx, head_ry, head_rz = 0.40, 0.38, 0.37
    elif sp == "sheep":
        head_rx, head_ry, head_rz = 0.40, 0.37, 0.38
    sc.add_ellipsoid(W(0.0, head_cy, 0.0), (S(head_rx * k), S(head_ry * k), S(head_rz * k)), c_fur, roughness=0.52)

    # 吻部（每種動物唔同 size / 長度，唔會全部似熊）
    muzzle_y = head_cy - 0.10
    mz = 0.30
    if sp == "cat":
        m_rx, m_ry, m_rz = 0.165, 0.115, 0.12
    elif sp == "fox":
        m_rx, m_ry, m_rz = 0.145, 0.115, 0.19
        mz = 0.315
        muzzle_y = head_cy - 0.13
    elif sp == "rabbit":
        m_rx, m_ry, m_rz = 0.150, 0.105, 0.115
        muzzle_y = head_cy - 0.12
    elif sp == "sheep":
        m_rx, m_ry, m_rz = 0.165, 0.120, 0.125
        muzzle_y = head_cy - 0.13
    elif sp in ("dog", "bear"):
        m_rx, m_ry, m_rz = 0.215, 0.150, 0.16
        muzzle_y = head_cy - 0.12
    else:  # panda
        m_rx, m_ry, m_rz = 0.185, 0.130, 0.135
        muzzle_y = head_cy - 0.12
    muzzle_col = c_soft
    if sp == "panda":
        muzzle_col = hex_rgb01("#F7F7F5")
    elif sp == "fox":
        muzzle_col = hex_rgb01("#FFF6EA")
    elif sp == "rabbit":
        muzzle_col = hex_rgb01("#F9F2F2")
    sc.add_ellipsoid(W(0.0, muzzle_y, mz), (S(m_rx), S(m_ry), S(m_rz)), muzzle_col, roughness=0.55)

    # 鼻（貓／兔細，狗／熊大）
    nose_r = 0.046 if sp in ("cat", "rabbit", "sheep") else (0.050 if sp == "fox" else 0.058)
    nose_col = hex_rgb01("#F29BA6") if sp == "rabbit" else hex_rgb01("#2A1E1A")
    sc.add_sphere(W(0.0, muzzle_y + 0.055, mz + m_rz * 0.86), S(nose_r), nose_col, roughness=0.30)
    # 嘴
    if expression == "surprised":
        sc.add_sphere(W(0.0, muzzle_y - 0.065, mz + m_rz * 0.72), S(0.052), hex_rgb01("#5A2B2B"), roughness=0.40)
    else:
        sc.add_ellipsoid(W(0.0, muzzle_y - 0.055, mz + m_rz * 0.74), (S(0.058), S(0.024), S(0.02)), hex_rgb01("#5A2B2B"), roughness=0.40)
    # 兔牙
    if sp == "rabbit":
        sc.add_rounded_box(W(0.0, muzzle_y - 0.105, mz + m_rz * 0.78), (S(0.050), S(0.055), S(0.018)), S(0.012), hex_rgb01("#FFFFFF"), roughness=0.35)
    # 狐狸白面頰（貼住面側，唔好橫跨鼻樑）
    if sp == "fox":
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(W(side * 0.245, muzzle_y - 0.04, mz + 0.02), (S(0.105), S(0.085), S(0.095)), hex_rgb01("#FFF6EA"), roughness=0.55)

    # 眼
    eye_y = head_cy + 0.075
    eye_z = 0.315
    eye_x = 0.185
    if sp == "rabbit":
        eye_x = 0.165
    blink = math.sin(t_sec * 2.15 + 0.9) > 0.986
    for side in (-1.0, 1.0):
        if sp == "panda":
            sc.add_ellipsoid(W(side * (eye_x + 0.01), eye_y, eye_z - 0.01), (S(0.145), S(0.155), S(0.105)), hex_rgb01("#222222"), roughness=0.55)
        if blink:
            sc.add_ellipsoid(W(side * eye_x, eye_y, eye_z + 0.01), (S(0.085), S(0.018), S(0.05)), hex_rgb01("#241815"), roughness=0.25)
            continue
        sc.add_sphere(W(side * eye_x, eye_y, eye_z), S(0.088 if expression != "surprised" else 0.10), hex_rgb01("#241815"), roughness=0.18)
        sc.add_sphere(W(side * (eye_x - 0.02), eye_y + 0.03, eye_z + 0.055), S(0.030), hex_rgb01("#FFFFFF"), roughness=0.10)
        sc.add_sphere(W(side * (eye_x + 0.03), eye_y - 0.03, eye_z + 0.05), S(0.014), hex_rgb01("#FFFFFF"), roughness=0.10)
    # 緊張眉毛
    if expression == "nervous":
        for side in (-1.0, 1.0):
            sc.add_capsule(W(side * (eye_x - 0.06), eye_y + 0.14, eye_z + 0.03), W(side * (eye_x + 0.07), eye_y + 0.18, eye_z + 0.02), S(0.016), hex_rgb01("#3A2A22"), roughness=0.5)

    if sp in ("cat", "fox"):
        ear_rx, ear_ry = (0.15, 0.22) if sp == "cat" else (0.17, 0.27)
        ear_y = head_cy + head_ry * 0.62
        for side in (-1.0, 1.0):
            rot = R @ rot_z(side * -18.0)
            sc.add_ellipsoid(W(side * (head_rx * 0.60), ear_y, -0.01), (S(ear_rx), S(ear_ry), S(0.075)), c_fur, rot=rot, roughness=0.50)
            sc.add_ellipsoid(W(side * (head_rx * 0.60), ear_y + 0.01, 0.035), (S(ear_rx * 0.58), S(ear_ry * 0.62), S(0.04)), hex_rgb01("#F2A9A2") if sp == "cat" else hex_rgb01("#3A2A22"), rot=rot, roughness=0.55)
    elif sp == "rabbit":
        ear_y = head_cy + head_ry * 0.62
        for side in (-1.0, 1.0):
            sc.add_capsule(W(side * 0.16, ear_y, -0.02), W(side * 0.28, ear_y + 0.44, -0.06), S(0.105), c_fur, roughness=0.55)
            sc.add_capsule(W(side * 0.17, ear_y + 0.02, 0.045), W(side * 0.27, ear_y + 0.38, 0.0), S(0.058), hex_rgb01("#F5B9BE"), roughness=0.55)
    elif sp == "dog":
        for side in (-1.0, 1.0):
            rot = R @ rot_z(side * 10.0)
            sc.add_ellipsoid(W(side * (head_rx * 0.92), head_cy - 0.02, 0.02), (S(0.10), S(0.23), S(0.14)), _shade(c_fur, 0.78), rot=rot, roughness=0.58)
    elif sp == "sheep":
        # 羊毛冠：一圈波波
        crown_y = head_cy + head_ry * 0.72
        for i in range(9):
            ang = (i / 9.0) * math.tau
            rr = 0.30 if i % 2 == 0 else 0.26
            sc.add_sphere(W(math.cos(ang) * rr, crown_y + math.sin(ang) * 0.10 + 0.04, -0.04 + math.sin(ang) * 0.20), S(0.155), hex_rgb01("#FBF7EE"), roughness=0.70)
        for i in range(12):
            ang = (i / 12.0) * math.tau
            sc.add_sphere(
                W(math.cos(ang) * 0.44, head_cy + math.sin(ang) * 0.40, 0.0),
                S(0.122) if i % 2 == 0 else S(0.104),
                hex_rgb01("#FBF7EE"), roughness=0.70,
            )
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(W(side * (head_rx * 1.06), head_cy + 0.02, 0.02), (S(0.10), S(0.055), S(0.15)), c_soft, roughness=0.60)
    elif sp in ("bear", "panda"):
        ear_col = c_fur if sp == "bear" else hex_rgb01("#222222")
        inner_col = c_soft if sp == "bear" else hex_rgb01("#4A4A4A")
        ear_y = head_cy + head_ry * 0.80
        for side in (-1.0, 1.0):
            sc.add_sphere(W(side * (head_rx * 0.66), ear_y, 0.0), S(0.145), ear_col, roughness=0.55)
            sc.add_sphere(W(side * (head_rx * 0.66), ear_y + 0.01, 0.075), S(0.085), inner_col, roughness=0.58)

    # 貓鬚
    if sp == "cat":
        for side in (-1.0, 1.0):
            for dy in (-0.02, 0.02):
                sc.add_capsule(W(side * 0.10, muzzle_y + dy, 0.36), W(side * 0.34, muzzle_y + dy + 0.05, 0.30), S(0.008), hex_rgb01("#4A382E"), roughness=0.4)


    # ---- 花紋（每種動物唔同）--------------------------------------------
    dark = _shade(c_fur, 0.55)
    eye_y_m = head_cy + 0.075
    if sp == "cat":
        # 額頭虎斑：兩邊斜紋，唔好連成一條粗眉
        for side in (-1.0, 1.0):
            for k in range(2):
                sc.add_capsule(
                    W(side * 0.050, head_cy + 0.340 - k * 0.070, 0.330 - k * 0.02),
                    W(side * 0.175, head_cy + 0.315 - k * 0.070, 0.290 - k * 0.02),
                    S(0.015), dark, roughness=0.55,
                )
    elif sp == "dog":
        # 一邊眼罩斑，另一邊乾淨 → 一眼認得
        sc.add_ellipsoid(
            W(-0.200, eye_y_m + 0.005, 0.255),
            (S(0.165), S(0.155), S(0.085)),
            _shade(c_fur, 0.45), roughness=0.55,
        )
        for side in (-1.0, 1.0):
            sc.add_sphere(W(side * (head_rx * 0.92), head_cy - 0.24, 0.02), S(0.085), _shade(c_fur, 0.70), roughness=0.58)
    elif sp == "fox":
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(
                W(side * (head_rx * 0.60), head_cy + head_ry * 0.74, -0.015),
                (S(0.10), S(0.12), S(0.06)),
                hex_rgb01("#3A2A22"), roughness=0.55,
            )
    # 腮紅（兔／羊／貓最可愛）
    if sp in ("rabbit", "sheep", "cat"):
        for side in (-1.0, 1.0):
            sc.add_ellipsoid(
                W(side * 0.285, head_cy - 0.135, 0.275),
                (S(0.065), S(0.042), S(0.028)),
                hex_rgb01("#F9BFC0"), roughness=0.62,
            )


def draw_animal_quadruped(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    species: str = "cat",
    fur: Optional[str] = None,
    outfit: Optional[Dict[str, Any]] = None,
    expression: str = "happy",
    t_sec: float = 0.0,
    walking: bool = True,
) -> None:
    """Four-legged animal with a trotting gait (same head kit as the biped rig)."""
    sp = str(species or "cat").lower().strip()
    if sp not in ANIMAL_FUR:
        sp = "cat"
    outfit = outfit if isinstance(outfit, dict) else {}
    style = str(outfit.get("style") or "").lower().strip()

    R = rot_y(yaw_deg)

    def W(x: float, y: float, z: float) -> np.ndarray:
        return base_pos + (R @ v3(x * scale, y * scale, z * scale))

    S = lambda v: float(v) * scale

    c_fur = _as_hex(fur, ANIMAL_FUR[sp])
    c_soft = _as_hex(ANIMAL_ACCENT.get(sp, "#FFFFFF"), ANIMAL_FUR[sp])
    c_top = _as_hex(outfit.get("top"), "#E8553E")
    c_accent = _as_hex(outfit.get("accent"), "#FFD24A")
    dark = _shade(c_fur, 0.55)

    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.05), strength=0.55)

    gait = math.sin(t_sec * 7.0) * 0.16 if walking else 0.0
    bob = math.sin(t_sec * 14.0) * 0.012 if walking else 0.0
    body_y = 0.74 + bob

    # ---- 身體 -----------------------------------------------------------
    sc.add_ellipsoid(W(0.0, body_y, 0.0), (S(0.295), S(0.285), S(0.56)), c_fur, roughness=0.55)
    sc.add_sphere(W(0.0, body_y + 0.04, 0.40), S(0.285), c_fur, roughness=0.55)
    sc.add_sphere(W(0.0, body_y + 0.02, -0.38), S(0.265), c_fur, roughness=0.55)
    sc.add_ellipsoid(W(0.0, body_y - 0.12, 0.06), (S(0.22), S(0.13), S(0.40)), c_soft, roughness=0.60)

    # ---- 四條腿（對角同步，細細步咁行）---------------------------------
    leg_col = _as_hex(ANIMAL_LIMB.get(sp), fur or ANIMAL_FUR[sp])
    for side in (-1.0, 1.0):
        for front, swing in ((1.0, gait), (-1.0, -gait)):
            z_hip = 0.32 * front
            z_knee = z_hip + swing * 0.35
            z_foot = z_hip + swing * 0.62
            sc.add_capsule(W(side * 0.215, 0.64 + bob, z_hip), W(side * 0.225, 0.38, z_knee), S(0.105), leg_col, roughness=0.55)
            sc.add_capsule(W(side * 0.225, 0.38, z_knee), W(side * 0.225, 0.10, z_foot), S(0.088), leg_col, roughness=0.55)
            sc.add_ellipsoid(W(side * 0.225, 0.09, z_foot + 0.045), (S(0.105), S(0.065), S(0.135)), leg_col, roughness=0.55)
    if sp == "panda":
        for side in (-1.0, 1.0):
            for front in (1.0, -1.0):
                sc.add_capsule(W(side * 0.215, 0.66 + bob, 0.30 * front), W(side * 0.225, 0.42, 0.30 * front), S(0.10), hex_rgb01("#222222"), roughness=0.55)

    # ---- 背部花紋 --------------------------------------------------------
    if sp == "cat":
        for k in range(3):
            sc.add_ellipsoid(W(0.0, body_y + 0.25 - k * 0.02, 0.16 - k * 0.20), (S(0.20), S(0.035), S(0.055)), dark, roughness=0.58)
    elif sp == "dog":
        for px, pz in ((-0.14, 0.10), (0.12, -0.18)):
            sc.add_sphere(W(px, body_y + 0.24, pz), S(0.085), dark, roughness=0.58)
    elif sp == "sheep":
        sc.add_ellipsoid(W(0.0, body_y + 0.08, 0.0), (S(0.325), S(0.315), S(0.545)), hex_rgb01("#FBF7EE"), roughness=0.72)
        for i in range(5):
            sc.add_sphere(
                W((-0.06 if i % 2 == 0 else 0.06), body_y + 0.40, -0.36 + i * 0.19),
                S(0.155), hex_rgb01("#FBF7EE"), roughness=0.74,
            )

    # ---- 頸 / 頭（同一套頭部元件）---------------------------------------
    sc.add_capsule(W(0.0, body_y + 0.16, 0.42), W(0.0, 1.06, 0.80), S(0.165), c_fur, roughness=0.55)
    _draw_animal_head(sc, W, S, R, sp, c_fur, c_soft, oy=-0.62, oz=0.84, expression=expression, t_sec=t_sec, head_scale=0.78)

    # ---- 背心 / 披風（四足動物嘅衫）-------------------------------------
    if style in ("cape", "armor", "spacesuit", "hoodie", "tee", "raincoat", "dress"):
        sc.add_ellipsoid(W(0.0, body_y + 0.235, 0.0), (S(0.285), S(0.055), S(0.38)), c_top, roughness=0.55)
        sc.add_ellipsoid(W(0.0, body_y + 0.255, 0.0), (S(0.20), S(0.02), S(0.075)), c_accent, roughness=0.55)
        if style in ("cape", "armor"):
            sc.add_rounded_box(W(0.0, body_y + 0.12, -0.44), (S(0.30), S(0.26), S(0.035)), S(0.06), _shade(c_top, 0.9), rot=R @ rot_x(8.0), roughness=0.58)

    # ---- 尾巴 -----------------------------------------------------------
    base_tail = (0.0, body_y + 0.16, -0.50)
    if sp == "cat":
        pts = [base_tail, (0.10, body_y + 0.34, -0.70), (0.05, body_y + 0.50, -0.82)]
        for a, b in zip(pts, pts[1:]):
            sc.add_capsule(W(*a), W(*b), S(0.055), c_fur, roughness=0.55)
        sc.add_sphere(W(*pts[-1]), S(0.055), c_soft, roughness=0.55)
    elif sp == "fox":
        sc.add_capsule(W(*base_tail), W(0.10, body_y + 0.42, -0.78), S(0.135), c_fur, roughness=0.62)
        sc.add_sphere(W(0.13, body_y + 0.50, -0.88), S(0.135), hex_rgb01("#FFF6EA"), roughness=0.62)
    elif sp == "sheep":
        sc.add_sphere(W(0.0, body_y + 0.14, -0.56), S(0.12), hex_rgb01("#FBF7EE"), roughness=0.72)
    elif sp == "rabbit":
        sc.add_sphere(W(0.0, body_y + 0.10, -0.56), S(0.115), hex_rgb01("#FFFFFF"), roughness=0.65)
    elif sp in ("bear", "panda"):
        sc.add_sphere(W(0.0, body_y + 0.10, -0.55), S(0.095), c_fur if sp == "bear" else hex_rgb01("#222222"), roughness=0.60)
    else:
        sc.add_capsule(W(*base_tail), W(0.14 + 0.05 * math.sin(t_sec * 9.0), body_y + 0.36, -0.70), S(0.065), c_fur, roughness=0.58)


def draw_animal_figure(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    species: str = "cat",
    fur: Optional[str] = None,
    outfit: Optional[Dict[str, Any]] = None,
    expression: str = "happy",
    t_sec: float = 0.0,
    wave: float = 0.0,
) -> None:
    """Draw a chibi bipedal animal built from scratch (no human head underneath).

    Proportions match the scout rig height (~2.15u) so species and humans can share a scene.
    `outfit` = {"style": tee|hoodie|dress|spacesuit|armor|cape|raincoat, "top", "bottom", "accent"}.
    """
    sp = str(species or "cat").lower().strip()
    if sp not in ANIMAL_FUR:
        sp = "cat"
    outfit = outfit if isinstance(outfit, dict) else {}
    style = str(outfit.get("style") or "tee").lower().strip()
    if style not in ("tee", "hoodie", "dress", "spacesuit", "armor", "cape", "raincoat"):
        style = "tee"

    R = rot_y(yaw_deg)

    def W(x: float, y: float, z: float) -> np.ndarray:
        return base_pos + (R @ v3(x * scale, y * scale, z * scale))

    S = lambda v: float(v) * scale

    c_fur = _as_hex(fur, ANIMAL_FUR[sp])
    c_soft = _as_hex(ANIMAL_ACCENT.get(sp, "#FFFFFF"), ANIMAL_FUR[sp])
    c_limb = _as_hex(ANIMAL_LIMB.get(sp), fur or ANIMAL_FUR[sp])
    c_shadowline = _shade(c_fur, 0.72)

    top_defaults = {
        "cat": "#E8553E", "sheep": "#7FB2E5", "dog": "#3E9E6B", "rabbit": "#E58FB8",
        "bear": "#8E6ED6", "fox": "#F2C14E", "panda": "#4D6FB5",
    }
    c_top = _as_hex(outfit.get("top"), top_defaults.get(sp, "#E8553E"))
    c_bottom = _as_hex(outfit.get("bottom"), "#31456B")
    c_accent = _as_hex(outfit.get("accent"), "#FFD24A")

    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.15), strength=0.55)

    bob = math.sin(t_sec * 3.2) * 0.015
    wave_u = float(max(0.0, min(1.0, wave)))
    arm_swing = math.sin(t_sec * 6.0) * 0.05

    # ---- 腿 / 腳 -------------------------------------------------------
    for side in (-1.0, 1.0):
        sc.add_capsule(W(side * 0.21, 0.12, 0.01), W(side * 0.20, 0.60, -0.01), S(0.145), c_limb, roughness=0.55)
        sc.add_ellipsoid(W(side * 0.21, 0.10, 0.10), (S(0.155), S(0.10), S(0.23)), c_limb, roughness=0.52)

    # ---- 下身 / 上身 ----------------------------------------------------
    sc.add_ellipsoid(W(0.0, 0.68 + bob, 0.0), (S(0.325), S(0.205), S(0.245)), c_bottom, roughness=0.55)
    if style in ("dress", "raincoat"):
        flare = 0.42 if style == "dress" else 0.37
        tiers = ((0.98, 0.84, flare * 0.68), (0.84, 0.70, flare * 0.82), (0.70, 0.56, flare))
        for ti, (y0, y1, rr) in enumerate(tiers):
            sc.add_cylinder(W(0.0, y0 + bob, 0.0), W(0.0, y1 + bob, 0.0), S(rr), c_top if ti % 2 == 0 else _shade(c_top, 0.92), roughness=0.52)
            sc.add_ellipsoid(W(0.0, y1 + bob, 0.0), (S(rr * 1.02), S(0.035), S(rr * 0.84)), c_accent, roughness=0.50)
    sc.add_ellipsoid(W(0.0, 1.02 + bob, 0.0), (S(0.34), S(0.30), S(0.25)), c_top, roughness=0.50)

    # ---- 手 / 掌 --------------------------------------------------------
    for side in (-1.0, 1.0):
        lift = 0.0
        if side > 0:
            lift = 0.30 * wave_u
        swing = arm_swing * side * (1.0 - wave_u)
        sh_p = (side * 0.30, 1.16 + bob, 0.0)
        elbow = (side * (0.42 + 0.02 * swing), 0.90 + lift * 0.4 + bob, 0.03)
        paw = (side * (0.47 + 0.05 * swing), 0.72 + lift * 1.1 + bob, 0.10)
        if side > 0 and wave_u > 0.05:
            paw = (0.52, 1.35 + bob, 0.16)
            elbow = (0.46, 1.02 + bob, 0.06)
        sc.add_capsule(W(*sh_p), W(*elbow), S(0.095), c_limb, roughness=0.52)
        sc.add_capsule(W(*elbow), W(*paw), S(0.085), c_limb, roughness=0.52)
        sc.add_sphere(W(*paw), S(0.105), c_soft if sp in ("rabbit", "cat") else c_limb, roughness=0.50)
        if style in ("tee", "hoodie", "spacesuit", "raincoat", "armor"):
            sleeve_end = (elbow[0], elbow[1] + 0.03, elbow[2])
            sc.add_capsule(W(*sh_p), W(*sleeve_end), S(0.125), c_top, roughness=0.50)

    # ---- 衫細節 ---------------------------------------------------------
    if style == "hoodie":
        sc.add_ellipsoid(W(0.0, 1.02 + bob, -0.16), (S(0.30), S(0.16), S(0.22)), _shade(c_top, 0.92), roughness=0.55)
        sc.add_rounded_box(W(0.0, 0.94 + bob, 0.245), (S(0.15), S(0.075), S(0.035)), S(0.03), _shade(c_accent, 0.95), roughness=0.55)
        sc.add_capsule(W(-0.07, 1.14 + bob, 0.24), W(-0.08, 1.02 + bob, 0.27), S(0.014), hex_rgb01("#F2F2F2"), roughness=0.4)
        sc.add_capsule(W(0.07, 1.14 + bob, 0.24), W(0.08, 1.02 + bob, 0.27), S(0.014), hex_rgb01("#F2F2F2"), roughness=0.4)
    elif style == "spacesuit":
        sc.add_rounded_box(W(0.0, 1.04 + bob, 0.24), (S(0.13), S(0.09), S(0.04)), S(0.03), hex_rgb01("#1B2A44"), roughness=0.25)
        for lx in (-0.05, 0.0, 0.05):
            sc.add_sphere(W(lx, 1.06 + bob, 0.285), S(0.018), hex_rgb01("#59E0FF"), roughness=0.15)
        sc.add_rounded_box(W(0.0, 1.02 + bob, -0.30), (S(0.22), S(0.22), S(0.10)), S(0.05), hex_rgb01("#D9DEE7"), roughness=0.40)
    elif style == "armor":
        sc.add_rounded_box(W(0.0, 1.06 + bob, 0.16), (S(0.30), S(0.20), S(0.13)), S(0.06), _shade(c_top, 1.0), roughness=0.28)
        for side in (-1.0, 1.0):
            sc.add_sphere(W(side * 0.34, 1.20 + bob, 0.0), S(0.15), c_accent, roughness=0.30)
        sc.add_rounded_box(W(0.0, 0.86 + bob, 0.26), (S(0.09), S(0.06), S(0.04)), S(0.02), c_accent, roughness=0.30)
    elif style == "cape":
        sc.add_rounded_box(W(0.0, 0.92 + bob, -0.30), (S(0.40), S(0.48), S(0.045)), S(0.10), _shade(c_top, 0.88), rot=R @ rot_x(6.0), roughness=0.60)
        sc.add_capsule(W(-0.24, 1.24 + bob, 0.02), W(0.0, 1.20 + bob, 0.26), S(0.05), c_accent, roughness=0.45)
        sc.add_capsule(W(0.24, 1.24 + bob, 0.02), W(0.0, 1.20 + bob, 0.26), S(0.05), c_accent, roughness=0.45)
    elif style in ("tee", "raincoat"):
        sc.add_ellipsoid(W(0.0, 1.235 + bob, 0.0), (S(0.22), S(0.055), S(0.20)), c_accent, roughness=0.50)
        sc.add_ellipsoid(W(0.0, 0.70 + bob, 0.0), (S(0.345), S(0.045), S(0.275)), c_accent, roughness=0.55)

    # ---- 頸 / 頭（由 _draw_animal_head 畫）------------------------------
    sc.add_capsule(W(0.0, 1.22 + bob, 0.0), W(0.0, 1.40 + bob, 0.0), S(0.14), c_fur, roughness=0.55)
    _draw_animal_head(sc, W, S, R, sp, c_fur, c_soft, dy=bob, expression=expression, t_sec=t_sec)

    # ---- 尾巴 -----------------------------------------------------------
    base_tail = (0.0, 0.76 + bob, -0.28)
    if sp == "cat":
        pts = [base_tail, (0.06, 0.98 + bob, -0.52), (0.02, 1.22 + bob, -0.60)]
        for a, b in zip(pts, pts[1:]):
            sc.add_capsule(W(*a), W(*b), S(0.062), c_fur, roughness=0.55)
        sc.add_sphere(W(*pts[-1]), S(0.062), c_soft, roughness=0.55)
    elif sp == "fox":
        sc.add_capsule(W(*base_tail), W(0.10, 1.02 + bob, -0.60), S(0.15), c_fur, roughness=0.62)
        sc.add_sphere(W(0.14, 1.10 + bob, -0.70), S(0.15), hex_rgb01("#FFF6EA"), roughness=0.62)
    elif sp == "sheep":
        sc.add_sphere(W(0.0, 0.82 + bob, -0.34), S(0.13), hex_rgb01("#FBF7EE"), roughness=0.70)
    elif sp == "rabbit":
        sc.add_sphere(W(0.0, 0.74 + bob, -0.34), S(0.125), hex_rgb01("#FFFFFF"), roughness=0.65)
    elif sp in ("bear", "panda"):
        sc.add_sphere(W(0.0, 0.74 + bob, -0.32), S(0.10), c_fur if sp == "bear" else hex_rgb01("#222222"), roughness=0.60)
    else:  # dog
        sc.add_capsule(W(*base_tail), W(0.16 + 0.05 * math.sin(t_sec * 9.0), 0.96 + bob, -0.50), S(0.07), c_fur, roughness=0.58)
