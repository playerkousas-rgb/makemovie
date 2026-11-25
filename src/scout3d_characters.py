"""3D Character & Prop Rigs for 'What If EP.01: 如果你有 SCOUT 3D':
- Bobo Smooth 3D Scout ('波波圓滑 3D 風' — hero style!)
- Blocky 3D Scout ('方塊 3D 風' — cameo comparison in Shot 2 & Shot 4!)
- Bobo Smooth 3D Mom & Bobo Smooth 3D Scout Leader
- Hero-Forge 3D Turntable Pedestal, 3D Handbook Stack, 3D Warning/Check Signs
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine3d import RGBf, Scene3D, hex_rgb01, normalize, rot_x, rot_y, rot_z, v3

# Official SCOUT3D-aligned color palette (converted to linear-friendly 0..1 RGB)
COL: Dict[str, RGBf] = {
    "skin": hex_rgb01("#F5CEB0"),
    "blush": hex_rgb01("#F08A7E"),
    "hair_dark": hex_rgb01("#3A2720"),
    "hair_mom": hex_rgb01("#4E3229"),
    "eye_dark": hex_rgb01("#231815"),
    "white": hex_rgb01("#FFFFFF"),
    "khaki": hex_rgb01("#CFB68C"),
    "khaki_dark": hex_rgb01("#AE946A"),
    "navy": hex_rgb01("#1F3052"),
    "maroon": hex_rgb01("#822030"),
    "yellow": hex_rgb01("#F0BA29"),
    "scout_green": hex_rgb01("#2E7D4F"),
    "scout_red": hex_rgb01("#C93B3B"),
    "world_purple": hex_rgb01("#6242AD"),
    "district_blue": hex_rgb01("#2A6FBD"),
    "mom_sweater": hex_rgb01("#E6736E"),
    "mom_skirt": hex_rgb01("#36496E"),
    "pedestal_top": hex_rgb01("#2C3548"),
    "pedestal_rim": hex_rgb01("#1E2533"),
    "gold": hex_rgb01("#F7C942"),
    "ok_green": hex_rgb01("#26B36B"),
    "warn_red": hex_rgb01("#E63946"),
    "sock": hex_rgb01("#F4F6F9"),
    "shoe": hex_rgb01("#2D4A7A"),
    "beret": hex_rgb01("#286643"),
    "beret_maroon": hex_rgb01("#7B1E2B"),
    "grasshopper_orange": hex_rgb01("#F2791C"),
    "air_blue": hex_rgb01("#8DB9E2"),
    "sea_white": hex_rgb01("#F2F6FA"),
    "venture_pants": hex_rgb01("#3A6347"),
    "necker_blue": hex_rgb01("#1F4E9C"),
    "tent_green": hex_rgb01("#3D7A5A"),
    "tent_tan": hex_rgb01("#E6D2B5"),
    "book_a": hex_rgb01("#3A6EA5"),
    "book_b": hex_rgb01("#C8553D"),
    "book_c": hex_rgb01("#4A7C59"),
    "pages": hex_rgb01("#FAF3E3"),
}


def draw_turntable_pedestal(
    sc: Scene3D, center_xz: Tuple[float, float] = (0.0, 0.0), y_top: float = 0.16, radius: float = 1.05
) -> None:
    """Signature SCOUT3D Hero-Forge dark circular 3D turntable base."""
    cx, cz = center_xz
    sc.add_floor_shadow(cx, cz, radius * 1.28, strength=0.34)
    sc.add_cylinder(v3(cx, 0.0, cz), v3(cx, y_top * 0.58, cz), radius * 1.06, COL["pedestal_rim"], roughness=0.38)
    sc.add_cylinder(v3(cx, y_top * 0.55, cz), v3(cx, y_top, cz), radius, COL["pedestal_top"], roughness=0.34)
    # Subtle glowing cyan/gold ring accent around turntable top
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


def get_scout_badge_slots_local() -> List[Dict]:
    """Return canonical 3D local coordinates & normals of HK Scout badges on a character
    standing with feet at y=0, facing +Z, Wearer's Left = +X, Wearer's Right = -X.
    """
    return [
        {
            "id": "membership",
            "pos": v3(0.21, 1.56, 0.285),    # Wearer's Left chest pocket: World Membership Badge
            "nrm": v3(0.12, 0.04, 0.99),
            "r": 0.078,
            "base": COL["world_purple"],
            "emb": COL["white"],
            "shape": "circle",
        },
        {
            "id": "link_award",
            "pos": v3(-0.21, 1.66, 0.275),   # Above Wearer's Right chest pocket
            "nrm": v3(-0.12, 0.06, 0.99),
            "r": 0.068,
            "base": COL["white"],
            "emb": COL["scout_green"],
            "shape": "diamond",
        },
        {
            "id": "troop_tape",
            "pos": v3(-0.565, 1.77, 0.02),   # Wearer's Right sleeve top (2 cm): Curved Troop Tape
            "nrm": v3(-0.98, 0.18, 0.05),
            "r": 0.095,
            "base": COL["maroon"],
            "emb": COL["yellow"],
            "shape": "tape",
        },
        {
            "id": "district",
            "pos": v3(-0.585, 1.61, 0.02),   # Wearer's Right sleeve mid (6.2 cm): District/Region
            "nrm": v3(-0.99, 0.06, 0.06),
            "r": 0.072,
            "base": COL["district_blue"],
            "emb": COL["gold"],
            "shape": "circle",
        },
        {
            "id": "patrol",
            "pos": v3(-0.60, 1.46, 0.02),    # Wearer's Right sleeve lower (15.4 cm): Patrol Badge
            "nrm": v3(-0.99, 0.02, 0.06),
            "r": 0.066,
            "base": COL["white"],
            "emb": COL["scout_red"],
            "shape": "diamond",
        },
        {
            "id": "prof_sleeve_1",
            "pos": v3(0.585, 1.63, 0.04),    # Wearer's Left sleeve: Proficiency Badge #1
            "nrm": v3(0.99, 0.06, 0.08),
            "r": 0.068,
            "base": COL["scout_green"],
            "emb": COL["gold"],
            "shape": "circle",
        },
        {
            "id": "prof_sleeve_2",
            "pos": v3(0.60, 1.48, -0.02),    # Wearer's Left sleeve: Proficiency Badge #2
            "nrm": v3(0.99, 0.02, -0.04),
            "r": 0.068,
            "base": COL["scout_green"],
            "emb": COL["gold"],
            "shape": "circle",
        },
    ]


def get_wrong_messy_badges_local() -> List[Dict]:
    """Hilariously misplaced badges in Shot 1 (before SCOUT 3D — belly, knee, forehead/wrong side!)."""
    return [
        {
            "pos": v3(0.06, 1.18, 0.30),     # Stuck crooked right on the belly!
            "nrm": v3(0.05, -0.08, 0.99),
            "r": 0.095,
            "base": COL["maroon"],
            "emb": COL["yellow"],
            "shape": "tape",
        },
        {
            "pos": v3(0.57, 1.74, 0.05),     # Troop/District badge sewed onto WRONG sleeve!
            "nrm": v3(0.98, 0.12, 0.08),
            "r": 0.080,
            "base": COL["district_blue"],
            "emb": COL["gold"],
            "shape": "circle",
        },
        {
            "pos": v3(-0.24, 1.35, 0.28),    # World Membership badge way down near waist!
            "nrm": v3(-0.15, -0.05, 0.98),
            "r": 0.082,
            "base": COL["world_purple"],
            "emb": COL["white"],
            "shape": "circle",
        },
        {
            "pos": v3(-0.20, 0.78, 0.23),    # Proficiency badge sewed onto navy shorts knee!!
            "nrm": v3(-0.08, 0.04, 0.99),
            "r": 0.075,
            "base": COL["scout_green"],
            "emb": COL["gold"],
            "shape": "diamond",
        },
    ]


# Section uniform color mapping (aligned with SCOUT3D v1.0)
SECTION_STYLES: Dict[str, Dict] = {
    "grasshopper": {
        "shirt": "grasshopper_orange",
        "pocket": "grasshopper_orange",
        "necker": "maroon",
        "woggle": "yellow",
        "bottom": "navy",
        "long_pants": False,
        "beret": None,
        "epaulette": None,
    },
    "cub": {
        "shirt": "khaki",
        "pocket": "khaki_dark",
        "necker": "yellow",
        "woggle": "scout_green",
        "bottom": "navy",
        "long_pants": False,
        "beret": None,
        "epaulette": None,
    },
    "scout": {
        "shirt": "khaki",
        "pocket": "khaki_dark",
        "necker": "maroon",
        "woggle": "yellow",
        "bottom": "navy",
        "long_pants": False,
        "beret": None,
        "epaulette": None,
    },
    "venture": {
        "shirt": "khaki",
        "pocket": "khaki_dark",
        "necker": "scout_green",
        "woggle": "khaki_dark",
        "bottom": "venture_pants",
        "long_pants": True,
        "beret": "beret_maroon",
        "epaulette": "beret_maroon",
    },
    "sea_scout": {
        "shirt": "sea_white",
        "pocket": "sea_white",
        "necker": "necker_blue",
        "woggle": "white",
        "bottom": "navy",
        "long_pants": False,
        "beret": None,
        "epaulette": "navy",
    },
    "air_scout": {
        "shirt": "air_blue",
        "pocket": "air_blue",
        "necker": "necker_blue",
        "woggle": "white",
        "bottom": "navy",
        "long_pants": True,
        "beret": None,
        "epaulette": "navy",
    },
}


def draw_scout_figure(
    sc: Scene3D,
    base_pos: np.ndarray,
    yaw_deg: float = 0.0,
    scale: float = 1.0,
    style_mode: str = "bobo",        # "bobo" (Smooth Rounded 3D) or "blocky" (Beveled Cube 3D)
    expression: str = "happy",       # "happy" | "nervous" | "surprised" | "proud"
    salute: float = 0.0,             # 0.0 = relaxed arms, 1.0 = crisp 3-finger Scout salute!
    badge_mode: str = "correct",     # "none" | "wrong" | "correct" | "animated"
    badge_progress: Optional[Dict[str, float]] = None,
    show_sash: float = 0.0,          # 0..1 visibility of green/red Proficiency Sash
    section: str = "scout",          # "grasshopper" | "cub" | "scout" | "venture" | "sea_scout" | "air_scout"
    gender: str = "M",               # "M" (curls) | "F" (twin pigtails)
    wave: float = 0.0,               # 0..1 cheerful left-hand wave
    t_sec: float = 0.0,
) -> None:
    """Draw a complete 3D Hong Kong Scout character at `base_pos` rotated by `yaw_deg`."""
    R = rot_y(yaw_deg)
    sec = SECTION_STYLES.get(section, SECTION_STYLES["scout"])
    c_shirt = COL[sec["shirt"]]
    c_pocket = COL[sec["pocket"]]
    c_necker = COL[sec["necker"]]
    c_woggle = COL[sec["woggle"]]
    c_bottom = COL[sec["bottom"]]
    long_pants = bool(sec["long_pants"])

    def W(lx: float, ly: float, lz: float) -> np.ndarray:
        return base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))

    def WN(nx: float, ny: float, nz: float) -> np.ndarray:
        return normalize(R @ v3(nx, ny, nz))

    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(0.58), strength=0.26)

    is_blocky = style_mode == "blocky"

    # --- 1. Shoes, Socks & Legs ---
    for side in (-1.0, 1.0):
        lx = side * 0.19
        if is_blocky:
            sc.add_rounded_box(W(lx, 0.09, 0.05), (S(0.11), S(0.09), S(0.17)), S(0.025), COL["shoe"], rot=R)
            if long_pants:
                sc.add_rounded_box(W(lx, 0.56, 0.0), (S(0.125), S(0.42), S(0.13)), S(0.025), c_bottom, rot=R)
            else:
                sc.add_rounded_box(W(lx, 0.24, 0.0), (S(0.095), S(0.08), S(0.095)), S(0.02), COL["sock"], rot=R)
                sc.add_rounded_box(W(lx, 0.52, 0.0), (S(0.10), S(0.22), S(0.10)), S(0.025), COL["skin"], rot=R)
                sc.add_rounded_box(W(lx, 0.84, 0.0), (S(0.125), S(0.16), S(0.135)), S(0.025), c_bottom, rot=R)
        else:
            sc.add_ellipsoid(W(lx, 0.09, 0.06), (S(0.12), S(0.09), S(0.18)), COL["shoe"], rot=R, roughness=0.40)
            if long_pants:
                sc.add_capsule(W(lx, 0.16, 0.0), W(lx, 0.96, 0.0), S(0.128), c_bottom, roughness=0.55)
            else:
                sc.add_capsule(W(lx, 0.16, 0.0), W(lx, 0.30, 0.0), S(0.098), COL["sock"], roughness=0.60)
                sc.add_capsule(W(lx, 0.30, 0.0), W(lx, 0.76, 0.0), S(0.095), COL["skin"], roughness=0.52)
                sc.add_capsule(W(lx, 0.72, 0.0), W(lx, 0.96, 0.0), S(0.135), c_bottom, roughness=0.55)

    # Shorts/Trousers Pelvis + Belt
    sc.add_rounded_box(
        W(0.0, 0.96, 0.0),
        (S(0.32), S(0.15), S(0.23)),
        S(0.04 if is_blocky else 0.12),
        c_bottom,
        rot=R,
        roughness=0.55,
    )
    sc.add_rounded_box(
        W(0.0, 1.10, 0.0),
        (S(0.33), S(0.045), S(0.245)),
        S(0.02 if is_blocky else 0.04),
        COL["hair_dark"],
        rot=R,
        roughness=0.40,
    )
    # Gold Scout belt buckle
    sc.add_rounded_box(W(0.0, 1.10, 0.25), (S(0.065), S(0.048), S(0.02)), S(0.012), COL["gold"], rot=R, roughness=0.25)

    # --- 2. Uniform Shirt Torso + Chest Pockets (+ Optional Epaulettes) ---
    sc.add_rounded_box(
        W(0.0, 1.48, 0.0),
        (S(0.34), S(0.36), S(0.25)),
        S(0.045 if is_blocky else 0.16),
        c_shirt,
        rot=R,
        roughness=0.52,
    )
    if section != "grasshopper":
        for side in (-1.0, 1.0):
            sc.add_rounded_box(
                W(side * 0.20, 1.54, 0.252),
                (S(0.095), S(0.105), S(0.025)),
                S(0.018),
                c_pocket,
                rot=R,
                roughness=0.55,
            )
    if sec["epaulette"]:
        for side in (-1.0, 1.0):
            sc.add_rounded_box(
                W(side * 0.26, 1.85, 0.0),
                (S(0.085), S(0.024), S(0.058)),
                S(0.012),
                COL[sec["epaulette"]],
                rot=R,
            )

    # --- 3. Proficiency Sash ('專章帶': Flat Tailored Green Ribbon with Red Trim, +X Shoulder -> -X Hip) ---
    if show_sash > 0.02:
        sa = min(1.0, show_sash)
        sash_rot = R @ rot_z(-39.5)
        # Front & back tailored flat sash ribbons: Red trim backing + proud Forest Green center!
        for z_sgn in (1.0, -1.0):
            sz = z_sgn * 0.262
            sc.add_rounded_box(
                W(-0.02, 1.49, sz),
                (S(0.088 * sa), S(0.45 * sa), S(0.015)),
                S(0.012),
                COL["scout_red"],
                rot=sash_rot,
                roughness=0.50,
            )
            sc.add_rounded_box(
                W(-0.02, 1.49, sz + z_sgn * 0.007),
                (S(0.060 * sa), S(0.45 * sa), S(0.016)),
                S(0.010),
                COL["scout_green"],
                rot=sash_rot,
                roughness=0.48,
            )
        # Smooth shoulder & waist wrap-over caps so sash wraps seamlessly around torso in 3D!
        sc.add_rounded_box(W(0.26, 1.83, 0.0), (S(0.085 * sa), S(0.028), S(0.27)), S(0.015), COL["scout_red"], rot=R)
        sc.add_rounded_box(W(0.26, 1.838, 0.0), (S(0.058 * sa), S(0.028), S(0.272)), S(0.012), COL["scout_green"], rot=R)
        sc.add_rounded_box(W(-0.31, 1.16, 0.0), (S(0.032), S(0.085 * sa), S(0.27)), S(0.015), COL["scout_red"], rot=R)
        sc.add_rounded_box(W(-0.316, 1.16, 0.0), (S(0.032), S(0.058 * sa), S(0.272)), S(0.012), COL["scout_green"], rot=R)

        # Crisp circular Proficiency Badges ('專科章') mounted flush along the front green sash!
        if sa > 0.65:
            for u_b in (0.22, 0.44, 0.66, 0.84):
                bx_s = 0.24 * (1.0 - u_b) + (-0.28) * u_b
                by_s = 1.80 * (1.0 - u_b) + 1.20 * u_b
                sc.add_scout_badge_3d(
                    W(bx_s, by_s, 0.288),
                    WN(0.0, 0.04, 1.0),
                    S(0.046),
                    COL["scout_green"],
                    COL["gold"],
                    shape="circle",
                )

    # --- 4. Scout Neckerchief ('旅巾') + Woggle ('巾圈') ---
    sc.add_capsule(W(-0.22, 1.84, 0.08), W(0.0, 1.66, 0.265), S(0.058), c_necker, roughness=0.50)
    sc.add_capsule(W(0.22, 1.84, 0.08), W(0.0, 1.66, 0.265), S(0.058), c_necker, roughness=0.50)
    sc.add_capsule(W(-0.22, 1.84, -0.10), W(0.22, 1.84, -0.10), S(0.055), c_necker, roughness=0.50)
    sc.add_rounded_box(W(0.0, 1.72, -0.255), (S(0.18), S(0.12), S(0.025)), S(0.02), c_necker, rot=R)
    sc.add_capsule(W(-0.02, 1.63, 0.27), W(-0.06, 1.42, 0.275), S(0.038), c_necker, roughness=0.50)
    sc.add_capsule(W(0.02, 1.63, 0.27), W(0.06, 1.42, 0.275), S(0.038), c_necker, roughness=0.50)
    sc.add_ellipsoid(W(0.0, 1.64, 0.285), (S(0.062), S(0.048), S(0.052)), c_woggle, rot=R, roughness=0.28)

    # --- 5. Left Arm (+X, relaxed or cheerful wave!) & Right Arm (-X, relaxed or 3-Finger Scout Salute!) ---
    wave_sw = math.sin(t_sec * 10.0) * 0.09 * wave
    l_sh = (0.43, 1.76, 0.0)
    l_el = (0.53 * (1.0 - wave) + 0.66 * wave, 1.48 * (1.0 - wave) + 1.84 * wave, 0.03 * (1.0 - wave) + 0.16 * wave)
    l_wr = (0.56 * (1.0 - wave) + (0.64 + wave_sw) * wave, 1.18 * (1.0 - wave) + 2.22 * wave, 0.06 * (1.0 - wave) + 0.24 * wave)
    if is_blocky and wave <= 0.02:
        sc.add_rounded_box(W(0.49, 1.62, 0.01), (S(0.105), S(0.18), S(0.11)), S(0.025), c_shirt, rot=R @ rot_z(14))
        sc.add_rounded_box(W(0.54, 1.32, 0.04), (S(0.085), S(0.16), S(0.085)), S(0.025), COL["skin"], rot=R @ rot_z(10))
        sc.add_rounded_box(W(*l_wr), (S(0.09), S(0.09), S(0.09)), S(0.03), COL["skin"], rot=R)
    else:
        sc.add_capsule(W(*l_sh), W(*l_el), S(0.118), c_shirt, roughness=0.52)
        sc.add_capsule(W(*l_el), W(*l_wr), S(0.088), COL["skin"], roughness=0.50)
        sc.add_sphere(W(l_wr[0], l_wr[1] - 0.04 * (1.0 - wave), l_wr[2]), S(0.096), COL["skin"], roughness=0.48)
        if wave <= 0.2:
            sc.add_capsule(W(l_wr[0] - 0.05, l_wr[1] - 0.02, l_wr[2] + 0.05), W(l_wr[0] - 0.07, l_wr[1] - 0.09, l_wr[2] + 0.07), S(0.038), COL["skin"])

    # Wearer's Right Arm (-X): blends from relaxed side (salute=0) to crisp 3-finger Scout Salute (salute=1)!
    r_sh = (-0.43, 1.76, 0.0)
    r_el = (-0.53 * (1.0 - salute) + (-0.68) * salute, 1.48 * (1.0 - salute) + 1.82 * salute, 0.03 * (1.0 - salute) + 0.18 * salute)
    r_wr = (-0.56 * (1.0 - salute) + (-0.44) * salute, 1.18 * (1.0 - salute) + 2.18 * salute, 0.06 * (1.0 - salute) + 0.28 * salute)

    if is_blocky:
        sc.add_capsule(W(*r_sh), W(*r_el), S(0.112), c_shirt, roughness=0.52)
        sc.add_capsule(W(*r_el), W(*r_wr), S(0.085), COL["skin"], roughness=0.50)
        sc.add_rounded_box(W(*r_wr), (S(0.078), S(0.075), S(0.068)), S(0.022), COL["skin"], rot=R)
    else:
        sc.add_capsule(W(*r_sh), W(*r_el), S(0.118), c_shirt, roughness=0.52)
        sc.add_capsule(W(*r_el), W(*r_wr), S(0.088), COL["skin"], roughness=0.50)
        sc.add_sphere(W(*r_wr), S(0.082), COL["skin"], roughness=0.48)

    if salute > 0.5:
        # Crisp 3-Finger Hong Kong Scout Salute for BOTH Bobo & Blocky Scouts! (Index, Middle, Ring + folded Thumb)
        for fx_off in (-0.036, 0.0, 0.036):
            sc.add_capsule(
                W(r_wr[0] + fx_off, r_wr[1] + 0.04, r_wr[2] + 0.01),
                W(r_wr[0] + fx_off * 0.92, r_wr[1] + 0.175, r_wr[2] + 0.01),
                S(0.022),
                COL["skin"],
                roughness=0.46,
            )
        # Thumb folded neatly across palm (pressing pinky — authentic Scout Salute!)
        sc.add_capsule(
            W(r_wr[0] + 0.045, r_wr[1] + 0.01, r_wr[2] + 0.055),
            W(r_wr[0] - 0.025, r_wr[1] + 0.035, r_wr[2] + 0.065),
            S(0.022),
            COL["skin"],
            roughness=0.46,
        )

    # --- 6. Neck, Head, High-Clearance 3D Hair & Expressive 3D Face ---
    sc.add_capsule(W(0.0, 1.80, 0.0), W(0.0, 1.98, 0.0), S(0.12), COL["skin"], roughness=0.50)

    head_cy = 2.26
    if is_blocky:
        sc.add_rounded_box(W(0.0, head_cy, 0.02), (S(0.33), S(0.31), S(0.31)), S(0.055), COL["skin"], rot=R, roughness=0.48)
        # Neat blocky hair cap strictly ABOVE forehead (y >= head_cy + 0.17 -> zero face occlusion!)
        sc.add_rounded_box(W(0.0, head_cy + 0.25, -0.01), (S(0.35), S(0.11), S(0.33)), S(0.04), COL["hair_dark"], rot=R, roughness=0.45)
        sc.add_rounded_box(W(0.0, head_cy + 0.02, -0.22), (S(0.34), S(0.24), S(0.12)), S(0.04), COL["hair_dark"], rot=R, roughness=0.45)
        face_z = 0.335
        ear_x = 0.35
    else:
        # Adorable plump '波波圓滑 3D' vinyl-toy head (like SCOUT3D og-image.png!)
        sc.add_ellipsoid(W(0.0, head_cy, 0.02), (S(0.38), S(0.35), S(0.35)), COL["skin"], rot=R, roughness=0.46)
        # Sculpted 3D rounded hair cap & high fluffy bangs STRICTLY above y = head_cy + 0.16!
        sc.add_ellipsoid(W(0.0, head_cy + 0.07, -0.05), (S(0.40), S(0.35), S(0.36)), COL["hair_dark"], rot=R, roughness=0.44)
        for bx_h, by_h, bz_h, br_h in [
            (-0.18, 0.26, 0.20, 0.14),
            (0.0, 0.28, 0.22, 0.15),
            (0.18, 0.26, 0.20, 0.14),
            (-0.30, 0.20, 0.12, 0.12),
            (0.30, 0.20, 0.12, 0.12),
        ]:
            sc.add_sphere(W(bx_h, head_cy + by_h, bz_h), S(br_h), COL["hair_dark"], roughness=0.42)
        face_z = 0.355
        ear_x = 0.38

    # Cute 3D ears (+ Girl Twin Pigtails & Venture Beret when selected!)
    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * ear_x, head_cy - 0.02, 0.02), (S(0.07), S(0.095), S(0.065)), COL["skin"], rot=R)
        if gender.upper() == "F":
            sc.add_sphere(W(side * 0.42, head_cy + 0.04, -0.06), S(0.11), COL["hair_mom"], roughness=0.42)
            sc.add_capsule(
                W(side * 0.44, head_cy + 0.02, -0.08),
                W(side * 0.50, head_cy - 0.20, -0.06),
                S(0.085),
                COL["hair_mom"],
                roughness=0.42,
            )

    if sec["beret"]:
        sc.add_ellipsoid(W(0.04, head_cy + 0.32, 0.02), (S(0.42), S(0.13), S(0.39)), COL[sec["beret"]], rot=R @ rot_z(-8), roughness=0.50)
        sc.add_sphere(W(-0.08, head_cy + 0.30, 0.38), S(0.050), COL["gold"], roughness=0.22)

    # Glossy 3D eyes + bright white catchlights + eyebrows (strictly clear below hair!)
    for side in (-1.0, 1.0):
        ex = side * 0.135
        ey = head_cy + 0.01
        sc.add_sphere(W(ex, ey, face_z - 0.01), S(0.046), COL["eye_dark"], roughness=0.12)
        sc.add_sphere(W(ex - 0.014, ey + 0.016, face_z + 0.028), S(0.015), COL["white"], roughness=0.05, emissive=(0.4, 0.4, 0.4))
        # Eyebrows (well below hair bangs at y = head_cy + 0.10!)
        if expression == "nervous":
            sc.add_capsule(
                W(ex - side * 0.045, head_cy + 0.115, face_z - 0.02),
                W(ex + side * 0.045, head_cy + 0.085, face_z - 0.02),
                S(0.016),
                COL["hair_dark"],
            )
        else:
            sc.add_capsule(
                W(ex - 0.045, head_cy + 0.105, face_z - 0.02),
                W(ex + 0.045, head_cy + 0.112, face_z - 0.02),
                S(0.016),
                COL["hair_dark"],
            )

    # Cute 3D button nose & rosy cheeks
    sc.add_sphere(W(0.0, head_cy - 0.045, face_z + 0.025), S(0.036), COL["skin"], roughness=0.42)
    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * 0.21, head_cy - 0.065, face_z - 0.045), (S(0.055), S(0.035), S(0.03)), COL["blush"], rot=R)

    # 3D Mouth expression
    if expression == "nervous":
        # Wavy nervous frown + 3D sweat drop
        sc.add_capsule(W(-0.07, head_cy - 0.145, face_z - 0.01), W(0.0, head_cy - 0.125, face_z), S(0.016), COL["maroon"])
        sc.add_capsule(W(0.0, head_cy - 0.125, face_z), W(0.07, head_cy - 0.145, face_z - 0.01), S(0.016), COL["maroon"])
        sc.add_ellipsoid(W(0.28, head_cy + 0.08, face_z - 0.05), (S(0.028), S(0.048), S(0.028)), hex_rgb01("#5EC8F8"), rot=R, roughness=0.15)
    elif expression == "surprised":
        sc.add_sphere(W(0.0, head_cy - 0.135, face_z), S(0.040), COL["maroon"])
    else:
        # Warm beaming happy/proud smile arc!
        sc.add_capsule(W(-0.085, head_cy - 0.115, face_z - 0.015), W(-0.03, head_cy - 0.145, face_z), S(0.018), COL["maroon"])
        sc.add_capsule(W(-0.03, head_cy - 0.145, face_z), W(0.03, head_cy - 0.145, face_z), S(0.018), COL["maroon"])
        sc.add_capsule(W(0.03, head_cy - 0.145, face_z), W(0.085, head_cy - 0.115, face_z - 0.015), S(0.018), COL["maroon"])

    # --- 7. 3D Surface-Snapped Scout Badges! ---
    if badge_mode == "wrong":
        for b in get_wrong_messy_badges_local():
            p = b["pos"]
            n = b["nrm"]
            sc.add_scout_badge_3d(
                W(float(p[0]), float(p[1]), float(p[2])),
                WN(float(n[0]), float(n[1]), float(n[2])),
                S(b["r"]),
                b["base"],
                b["emb"],
                shape=b["shape"],
            )
    elif badge_mode in ("correct", "animated"):
        # Compute dynamic right-upper-arm frame so sleeve badges track the arm cleanly during salute!
        r_sh_v = v3(*r_sh)
        r_el_v = v3(*r_el)
        r_arm_axis = normalize(r_el_v - r_sh_v)
        # Outward sleeve normal perpendicular to upper arm (pointing toward -X / +Z front-outer)
        r_out_nrm = normalize(np.cross(r_arm_axis, v3(0.0, 0.0, -1.0)))
        if r_out_nrm[0] > 0:
            r_out_nrm = -r_out_nrm

        for b in get_scout_badge_slots_local():
            prog = 1.0 if (badge_progress is None) else badge_progress.get(b["id"], 1.0)
            if prog <= 0.01:
                continue
            target_p = b["pos"]
            n = b["nrm"]
            # If right-sleeve badge & arm is saluting, attach cleanly to the raised khaki upper sleeve!
            if salute > 0.02 and b["id"] in ("troop_tape", "district", "patrol"):
                u_along = {"troop_tape": 0.22, "district": 0.52, "patrol": 0.80}[b["id"]]
                arm_pt = r_sh_v * (1.0 - u_along) + r_el_v * u_along + r_out_nrm * 0.125
                target_p = target_p * (1.0 - salute) + arm_pt * salute
                n = normalize(n * (1.0 - salute) + r_out_nrm * salute)

            # Fly in along a snappy 3D arc when 0 < prog < 1!
            fly_t = min(1.0, prog)
            ease = 1.0 - (1.0 - fly_t) ** 3
            start_p = target_p + v3(0.85 * (1.0 if target_p[0] >= 0 else -1.0), 0.45, 0.75)
            cur_p = start_p * (1.0 - ease) + target_p * ease
            pop_scale = 1.0 + 0.28 * math.sin(fly_t * math.pi) if fly_t < 0.99 else 1.0
            glow_amt = 0.55 * (1.0 - fly_t) if fly_t < 0.99 else 0.0
            sc.add_scout_badge_3d(
                W(float(cur_p[0]), float(cur_p[1]), float(cur_p[2])),
                WN(float(n[0]), float(n[1]), float(n[2])),
                S(b["r"] * pop_scale),
                b["base"],
                b["emb"],
                shape=b["shape"],
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

    # Navy skirt + cozy coral-rose sweater
    sc.add_cylinder(W(0.0, 0.72, 0.0), W(0.0, 1.12, 0.0), S(0.36), COL["mom_skirt"], roughness=0.55)
    sc.add_rounded_box(W(0.0, 1.48, 0.0), (S(0.34), S(0.36), S(0.25)), S(0.17), COL["mom_sweater"], rot=R, roughness=0.52)
    sc.add_ellipsoid(W(0.0, 1.82, 0.08), (S(0.20), S(0.06), S(0.16)), COL["white"], rot=R)

    # Arms (gesturing happily or holding sewing needle/head)
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

    # Neck, smooth round head & cute high top-bun (strictly above forehead!)
    sc.add_capsule(W(0.0, 1.82, 0.0), W(0.0, 1.98, 0.0), S(0.115), COL["skin"])
    hy = 2.26
    sc.add_ellipsoid(W(0.0, hy, 0.02), (S(0.37), S(0.35), S(0.35)), COL["skin"], rot=R, roughness=0.46)
    sc.add_ellipsoid(W(0.0, hy + 0.08, -0.06), (S(0.39), S(0.35), S(0.36)), COL["hair_mom"], rot=R, roughness=0.44)
    # High round Mom bun on top of head!
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
        # Orbiting 3D dizzy stars above Mom's head!
        for k in range(3):
            ang = t_sec * 4.5 + k * (2.0 * math.pi / 3.0)
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
    scale: float = 1.08,
    mood: str = "scold",  # "scold" | "praise"
    t_sec: float = 0.0,
) -> None:
    """Adorable '波波圓滑 3D' Adult Scout Leader (Green Beret + Khaki Uniform + Red X or Green Check/Thumbs-Up!)."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(0.62), strength=0.28)

    # Long navy uniform trousers & shoes
    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * 0.19, 0.09, 0.06), (S(0.12), S(0.09), S(0.18)), COL["eye_dark"], rot=R)
        sc.add_capsule(W(side * 0.19, 0.16, 0.0), W(side * 0.19, 0.96, 0.0), S(0.13), COL["navy"], roughness=0.55)

    sc.add_rounded_box(W(0.0, 0.98, 0.0), (S(0.33), S(0.14), S(0.24)), S(0.12), COL["navy"], rot=R)
    sc.add_rounded_box(W(0.0, 1.50, 0.0), (S(0.36), S(0.38), S(0.26)), S(0.16), COL["khaki"], rot=R, roughness=0.50)
    # Leader Maroon/Gilwell Neckerchief + Epaulettes
    for side in (-1.0, 1.0):
        sc.add_rounded_box(W(side * 0.28, 1.88, 0.0), (S(0.09), S(0.025), S(0.06)), S(0.015), COL["maroon"], rot=R)
    sc.add_capsule(W(-0.22, 1.86, 0.08), W(0.0, 1.66, 0.275), S(0.060), COL["maroon"])
    sc.add_capsule(W(0.22, 1.86, 0.08), W(0.0, 1.66, 0.275), S(0.060), COL["maroon"])
    sc.add_ellipsoid(W(0.0, 1.65, 0.295), (S(0.062), S(0.05), S(0.05)), COL["khaki_dark"], rot=R)
    # Leader ribbon bar above right pocket!
    sc.add_rounded_box(W(-0.21, 1.68, 0.27), (S(0.09), S(0.028), S(0.02)), S(0.01), COL["scout_green"], rot=R)

    # Arms + 3D Verdict Sign (Red X in Shot 1 vs Thumbs-Up + Green Check in Shot 4!)
    bob = math.sin(t_sec * 5.0) * 0.04
    if mood == "scold":
        sc.add_capsule(W(0.45, 1.78, 0.0), W(0.54, 1.24, 0.08), S(0.115), COL["khaki"])
        sc.add_sphere(W(0.55, 1.18, 0.09), S(0.098), COL["skin"])
        # Pointing / raising Red X warning sign high in open air!
        sc.add_capsule(W(-0.45, 1.78, 0.0), W(-0.56, 2.18 + bob, 0.24), S(0.115), COL["khaki"])
        sc.add_sphere(W(-0.58, 2.25 + bob, 0.26), S(0.098), COL["skin"])
        sx_c, sy_c, sz_c = -0.52, 2.92 + bob, 0.34
        sc.add_cylinder(W(sx_c, sy_c, sz_c - 0.04), W(sx_c, sy_c, sz_c + 0.04), S(0.26), COL["warn_red"], roughness=0.30, emissive=(0.25, 0.02, 0.02))
        sc.add_capsule(W(sx_c - 0.12, sy_c - 0.12, sz_c + 0.06), W(sx_c + 0.12, sy_c + 0.12, sz_c + 0.06), S(0.042), COL["white"])
        sc.add_capsule(W(sx_c - 0.12, sy_c + 0.12, sz_c + 0.06), W(sx_c + 0.12, sy_c - 0.12, sz_c + 0.06), S(0.042), COL["white"])
    else:
        # Relaxed inner arm + Big Unobstructed Outer Thumbs-Up + Glowing Green Checkmark Shield!
        sc.add_capsule(W(-0.44, 1.76, 0.0), W(-0.48, 1.24, 0.08), S(0.112), COL["khaki"])
        sc.add_sphere(W(-0.49, 1.18, 0.09), S(0.094), COL["skin"])

        sc.add_capsule(W(0.44, 1.78, 0.0), W(0.54, 1.84 + bob, 0.38), S(0.115), COL["khaki"])
        sc.add_sphere(W(0.54, 1.86 + bob, 0.42), S(0.104), COL["skin"])
        # Big clear 3D Thumb pointing straight up!
        sc.add_capsule(W(0.54, 1.93 + bob, 0.42), W(0.54, 2.13 + bob, 0.42), S(0.046), COL["skin"])
        # Floating 3D Green Check badge cleanly above heads!
        sx_c, sy_c, sz_c = -0.38, 2.94 + bob, 0.36
        sc.add_cylinder(W(sx_c, sy_c, sz_c - 0.04), W(sx_c, sy_c, sz_c + 0.04), S(0.27), COL["ok_green"], roughness=0.28, emissive=(0.04, 0.25, 0.10))
        sc.add_capsule(W(sx_c - 0.12, sy_c - 0.01, sz_c + 0.06), W(sx_c - 0.02, sy_c - 0.11, sz_c + 0.06), S(0.042), COL["white"])
        sc.add_capsule(W(sx_c - 0.02, sy_c - 0.11, sz_c + 0.06), W(sx_c + 0.14, sy_c + 0.11, sz_c + 0.06), S(0.042), COL["white"])

    # Head + Classic Scout Green Beret (high above eyebrows -> zero face occlusion!)
    sc.add_capsule(W(0.0, 1.84, 0.0), W(0.0, 2.00, 0.0), S(0.12), COL["skin"])
    hy = 2.28
    sc.add_ellipsoid(W(0.0, hy, 0.02), (S(0.38), S(0.35), S(0.35)), COL["skin"], rot=R, roughness=0.46)
    sc.add_ellipsoid(W(0.0, hy + 0.06, -0.07), (S(0.39), S(0.32), S(0.35)), COL["hair_dark"], rot=R)
    # Green Scout Beret tilted stylishly above forehead!
    sc.add_ellipsoid(W(0.04, hy + 0.31, 0.02), (S(0.42), S(0.14), S(0.39)), COL["beret"], rot=R @ rot_z(-8), roughness=0.52)
    sc.add_sphere(W(-0.08, hy + 0.29, 0.38), S(0.055), COL["gold"], roughness=0.22)

    fz = 0.355
    for side in (-1.0, 1.0):
        sc.add_ellipsoid(W(side * 0.38, hy - 0.02, 0.02), (S(0.07), S(0.095), S(0.065)), COL["skin"], rot=R)
        ex = side * 0.135
        sc.add_sphere(W(ex, hy + 0.01, fz - 0.01), S(0.046), COL["eye_dark"], roughness=0.12)
        sc.add_sphere(W(ex - 0.014, hy + 0.016, fz + 0.026), S(0.014), COL["white"], roughness=0.05, emissive=(0.4, 0.4, 0.4))
        if mood == "scold":
            # Stern angled scolding eyebrows!
            sc.add_capsule(
                W(ex - side * 0.05, hy + 0.085, fz - 0.01),
                W(ex + side * 0.05, hy + 0.135, fz - 0.02),
                S(0.020),
                COL["hair_dark"],
            )
        else:
            sc.add_capsule(
                W(ex - 0.045, hy + 0.115, fz - 0.02),
                W(ex + 0.045, hy + 0.120, fz - 0.02),
                S(0.018),
                COL["hair_dark"],
            )
            sc.add_ellipsoid(W(side * 0.21, hy - 0.065, fz - 0.045), (S(0.055), S(0.035), S(0.03)), COL["blush"], rot=R)

    sc.add_sphere(W(0.0, hy - 0.045, fz + 0.025), S(0.038), COL["skin"])
    if mood == "scold":
        sc.add_capsule(W(-0.075, hy - 0.148, fz - 0.01), W(0.0, hy - 0.118, fz), S(0.020), COL["maroon"])
        sc.add_capsule(W(0.0, hy - 0.118, fz), W(0.075, hy - 0.148, fz - 0.01), S(0.020), COL["maroon"])
    else:
        sc.add_capsule(W(-0.09, hy - 0.110, fz - 0.015), W(0.0, hy - 0.150, fz), S(0.020), COL["maroon"])
        sc.add_capsule(W(0.0, hy - 0.150, fz), W(0.09, hy - 0.110, fz - 0.015), S(0.020), COL["maroon"])


def draw_handbook_stack(sc: Scene3D, base_pos: np.ndarray, yaw_deg: float = 0.0, scale: float = 1.0) -> None:
    """Giant intimidating stack of 3 thick uniform manuals (zero baked text!)."""
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
    """Cute 3D Scout A-Frame Camp Tent prop for outdoor camp episodes."""
    R = rot_y(yaw_deg)
    W = lambda lx, ly, lz: base_pos + (R @ v3(lx * scale, ly * scale, lz * scale))
    S = lambda d: d * scale
    sc.add_floor_shadow(float(base_pos[0]), float(base_pos[2]), S(1.05), strength=0.22)
    # Left & right canvas roof panels
    sc.add_rounded_box(W(-0.36, 0.54, 0.0), (S(0.50), S(0.045), S(0.62)), S(0.02), COL["tent_green"], rot=R @ rot_z(48), roughness=0.65)
    sc.add_rounded_box(W(0.36, 0.54, 0.0), (S(0.50), S(0.045), S(0.62)), S(0.02), COL["tent_green"], rot=R @ rot_z(-48), roughness=0.65)
    # Ridge pole + front/back wooden poles
    sc.add_capsule(W(0.0, 0.96, -0.66), W(0.0, 0.96, 0.66), S(0.038), COL["khaki_dark"], roughness=0.55)
    sc.add_capsule(W(0.0, 0.0, 0.64), W(0.0, 1.04, 0.64), S(0.036), COL["khaki_dark"], roughness=0.55)
    sc.add_capsule(W(0.0, 0.0, -0.64), W(0.0, 1.04, -0.64), S(0.036), COL["khaki_dark"], roughness=0.55)
    # Cozy warm interior mat
    sc.add_rounded_box(W(0.0, 0.04, 0.0), (S(0.56), S(0.035), S(0.58)), S(0.02), COL["tent_tan"], rot=R, roughness=0.70)

