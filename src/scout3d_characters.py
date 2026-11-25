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

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

from engine3d import RGBf, Scene3D, hex_rgb01, normalize, rot_x, rot_y, rot_z, v3

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


def _get_badge_rgba(rel_file: str) -> Optional[np.ndarray]:
    if not rel_file:
        return None
    clean = rel_file.lstrip("/")
    if clean.startswith("badges/"):
        clean = clean[len("badges/") :]
    if clean in _TEX_CACHE:
        return _TEX_CACHE[clean]
    full = BADGE_DIR / clean
    if not full.is_file():
        return None
    img = Image.open(full).convert("RGBA")
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

    sec = section.lower().strip()
    sash_supported = sec in ("scout", "sea_scout", "air_scout")
    sash_amt = float(max(0.0, min(1.0, show_sash))) if sash_supported else 0.0
    use_sash_layout = sash_supported and (sash_amt > 0.05)

    variant, gen_entry, badges = _select_rig_bundle(sec, gender, use_sash_layout)
    L = gen_entry["layout"]
    B = L["B"]
    strap = gen_entry.get("strap")
    sash_cfg = gen_entry.get("sash")

    is_blocky = style_mode == "blocky"
    is_girl = str(gender).upper().startswith(("F", "G"))
    wear_hat = bool(hat) if hat is not None else (sec in ("venture", "leader"))

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
                    COL["skin"],
                    rot=R,
                    roughness=0.50,
                )
            else:
                sc.add_capsule(W(lx, leg["y"] + 0.8, 0.0), W(lx, sock_top, 0.0), S_cm(leg_hw * 0.86), c_sock, roughness=0.58)
                sc.add_capsule(W(lx, sock_top - 0.4, 0.0), W(lx, shorts_bot + 1.2, 0.0), S_cm(leg_hw * 0.84), COL["skin"], roughness=0.50)

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

    if B.get("pocket"):
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
    R_upper_l = rot_z(-132.0 * wave_u - wave_osc * 0.4) @ rot_x(-18.0 * wave_u)
    l_elbow = l_pivot + (R_upper_l @ v3(0.0, -float(u_arm["h"]), 0.0))
    l_sleeve_mid = l_pivot + (R_upper_l @ v3(0.0, -sleeve_len * 0.5 + 1.0, 0.0))

    slv_hd = slv["d"] * 0.50
    slv_bevel = 0.45 if is_blocky else 1.35

    sc.add_rounded_box(
        WV(l_sleeve_mid),
        (S_cm(slv["w"] * 0.5), S_cm(sleeve_len * 0.5), S_cm(slv_hd)),
        S_cm(slv_bevel),
        c_shirt,
        rot=R @ R_upper_l,
        roughness=0.52,
    )
    R_fore_l = R_upper_l @ rot_z(-18.0 * wave_u - wave_osc)
    l_wrist = l_elbow + (R_fore_l @ v3(0.0, -forearm_len, 0.0))
    if is_blocky:
        sc.add_rounded_box(
            WV(0.5 * (l_elbow + l_wrist)),
            (S_cm(l_arm["w"] * 0.5), S_cm(forearm_len * 0.52), S_cm(l_arm["d"] * 0.5)),
            S_cm(0.4),
            COL["skin"],
            rot=R @ R_fore_l,
            roughness=0.50,
        )
        sc.add_rounded_box(
            WV(l_wrist + (R_fore_l @ v3(0.0, -hand["h"] * 0.38, 0.0))),
            (S_cm(hand["w"] * 0.5), S_cm(hand["h"] * 0.45), S_cm(hand["d"] * 0.5)),
            S_cm(0.4),
            COL["skin"],
            rot=R @ R_fore_l,
            roughness=0.48,
        )
    else:
        sc.add_capsule(WV(l_elbow), WV(l_wrist), S_cm(l_arm["w"] * 0.48), COL["skin"], roughness=0.50)
        sc.add_sphere(WV(l_wrist + (R_fore_l @ v3(0.0, -hand["h"] * 0.30, 0.0))), S_cm(hand["w"] * 0.56), COL["skin"], roughness=0.48)

    # --- Wearer's RIGHT Arm (-X): relaxed at 0.0 -> crisp 3-finger HK Scout Salute at 1.0 ---
    r_pivot = v3(-float(L["armX"]), float(L["shoulderY"]), 0.0)
    sal_u = float(max(0.0, min(1.0, salute)))
    # Lift right elbow outward (-X) and slightly forward (+Z) so all right-sleeve badges stay readable
    R_upper_r = rot_x(-24.0 * sal_u) @ rot_z(-40.0 * sal_u)
    r_elbow = r_pivot + (R_upper_r @ v3(0.0, -float(u_arm["h"]), 0.0))
    r_sleeve_mid = r_pivot + (R_upper_r @ v3(0.0, -sleeve_len * 0.5 + 1.0, 0.0))

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
            COL["skin"],
            rot=R,
            roughness=0.50,
        )
        sc.add_rounded_box(
            WV(r_wrist + v3(0.0, -hand["h"] * 0.38, 0.0)),
            (S_cm(hand["w"] * 0.5), S_cm(hand["h"] * 0.45), S_cm(hand["d"] * 0.5)),
            S_cm(0.4),
            COL["skin"],
            rot=R,
            roughness=0.48,
        )
    else:
        sc.add_capsule(WV(r_elbow), WV(r_wrist), S_cm(l_arm["w"] * 0.48), COL["skin"], roughness=0.50)
        sc.add_sphere(WV(r_wrist), S_cm(hand["w"] * 0.52), COL["skin"], roughness=0.48)

    if sal_u > 0.5:
        for fx_cm in (-1.30, 0.0, 1.30):
            sc.add_capsule(
                WV(r_wrist + v3(fx_cm, 1.2, 0.2)),
                WV(r_wrist + v3(fx_cm * 0.88 + 0.8, 6.2, 0.2)),
                S_cm(0.70),
                COL["skin"],
                roughness=0.46,
            )
        sc.add_capsule(WV(r_wrist + v3(1.6, 0.4, 1.5)), WV(r_wrist + v3(-0.8, 1.5, 1.7)), S_cm(0.70), COL["skin"], roughness=0.46)

    # =========================================================================
    # 6. NECK, HEAD, HAIR, OPTIONAL SECTION HEADWEAR & EXPRESSIVE FACE
    # =========================================================================
    neck = B["neck"]
    sc.add_capsule(W(0.0, neck["y"] - 0.5, 0.0), W(0.0, head["y"] + 2.0, head["z"] * 0.5), S_cm(neck["w"] * 0.42), COL["skin"], roughness=0.50)

    head_cy = head["y"] + head["h"] * 0.5
    head_hw = head["w"] * 0.5
    head_hh = head["h"] * 0.5
    head_hd = head["d"] * 0.5
    hz = head["z"]

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
        s_key = p["key"]
        s_id = p["id"]
        rel_file = p.get("art")
        if not rel_file:
            continue

        is_sash_badge = bool(p.get("onSash"))
        if is_sash_badge and sash_amt < 0.55:
            continue

        prog = 1.0 if badge_mode == "correct" else _slot_progress(s_key, s_id, badge_progress)
        if prog <= 0.01:
            continue

        tex = _get_badge_rgba(rel_file)
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
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(0.60), strength=0.26)

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
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(0.55), strength=0.25)

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
    """3D Scout A-Frame Camp Tent prop for outdoor camp episodes."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.05), strength=0.22)
    sc.add_rounded_box(W(-0.36, 0.54, 0.0), (S(0.50), S(0.045), S(0.62)), S(0.02), COL["tent_green"], rot=R @ rot_z(48), roughness=0.65)
    sc.add_rounded_box(W(0.36, 0.54, 0.0), (S(0.50), S(0.045), S(0.62)), S(0.02), COL["tent_green"], rot=R @ rot_z(-48), roughness=0.65)
    sc.add_capsule(W(0.0, 0.96, -0.66), W(0.0, 0.96, 0.66), S(0.038), COL["khaki_dark"], roughness=0.55)
    sc.add_capsule(W(0.0, 0.0, 0.64), W(0.0, 1.04, 0.64), S(0.036), COL["khaki_dark"], roughness=0.55)
    sc.add_capsule(W(0.0, 0.0, -0.64), W(0.0, 1.04, -0.64), S(0.036), COL["khaki_dark"], roughness=0.55)
    sc.add_rounded_box(W(0.0, 0.04, 0.0), (S(0.56), S(0.035), S(0.58)), S(0.02), COL["tent_tan"], rot=R, roughness=0.70)
