"""Shared character rig, 5-finger anatomical hands, tea egg prop, and steam plumes.
100% coordinate-locked across Version A (Crayon) and Version B (16-bit Pixel).
"""

from __future__ import annotations

import math
from typing import List, Tuple

from camera import CameraState, clamp, lerp, smoothstep
from style_backends import Point, StyleCanvas


def _capsule_points(
    x0: float, y0: float, x1: float, y1: float, r0: float, r1: float, steps_cap: int = 8
) -> List[Point]:
    """Construct a smooth tapered limb/finger capsule polygon from (x0,y0,r0) to (x1,y1,r1)."""
    dx = x1 - x0
    dy = y1 - y0
    ang = math.atan2(dy, dx)
    pts: List[Point] = []
    for i in range(steps_cap + 1):
        th = ang + math.pi * 0.5 + math.pi * (i / float(steps_cap))
        pts.append((x0 + r0 * math.cos(th), y0 + r0 * math.sin(th)))
    for i in range(steps_cap + 1):
        th = ang - math.pi * 0.5 + math.pi * (i / float(steps_cap))
        pts.append((x1 + r1 * math.cos(th), y1 + r1 * math.sin(th)))
    return pts


def _solve_two_bone_ik(
    sx: float, sy: float, tx: float, ty: float, l1: float, l2: float, bend_down: bool = True
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Exact 2-bone analytical IK so upper arm (l1) and forearm (l2) NEVER stretch or deform."""
    dx = tx - sx
    dy = ty - sy
    dist = math.hypot(dx, dy)
    # Keep a natural soft anatomical bend (never hyper-extended 180 deg stick!)
    max_reach = (l1 + l2) * 0.965
    min_reach = abs(l1 - l2) + 8.0
    if dist > max_reach:
        scale = max_reach / dist
        dx *= scale
        dy *= scale
        dist = max_reach
    elif dist < min_reach:
        scale = min_reach / max(1e-4, dist)
        dx *= scale
        dy *= scale
        dist = min_reach

    wx, wy = sx + dx, sy + dy
    cos_a = clamp((l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist), -1.0, 1.0)
    a = math.acos(cos_a)
    base_ang = math.atan2(dy, dx)
    elbow_ang = base_ang + (a if bend_down else -a)
    ex = sx + l1 * math.cos(elbow_ang)
    ey = sy + l1 * math.sin(elbow_ang)
    return (ex, ey), (wx, wy)


def draw_tea_egg(
    cv: StyleCanvas,
    cam: CameraState,
    wx: float,
    wy: float,
    scale: float = 1.0,
    tilt_deg: float = 0.0,
    seed: int = 101,
) -> None:
    """Draw a marbled cracked tea egg with authentic avian egg contour and 7 tea-broth veins."""
    cx, cy = cam.project(wx, wy)
    rx = cam.scale(24.0 * scale)
    ry = cam.scale(31.0 * scale)
    ang = math.radians(tilt_deg)
    ca, sa = math.cos(ang), math.sin(ang)

    def _egg_pt(u: float, v: float) -> Point:
        taper = 1.0 + 0.13 * v
        lx = u * rx * taper
        ly = v * ry
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)

    contour: List[Point] = []
    num = 36
    for i in range(num):
        th = 2.0 * math.pi * i / float(num)
        u = math.sin(th)
        v = -math.cos(th)
        contour.append(_egg_pt(u, v))

    # 1. Base tea-stained shell fill
    cv.polygon(
        contour,
        fill_key="egg",
        outline_key=None,
        tooth_amount=0.10,
        shade_key="broth_light",
        seed=seed,
    )

    # 2. Warm moist specular highlight spot on upper-right
    hx, hy = _egg_pt(0.34, -0.44)
    cv.ellipse(
        hx,
        hy,
        rx * 0.22,
        ry * 0.16,
        angle_deg=tilt_deg - 28.0,
        fill_key="egg_light",
        outline_key=None,
        tooth_amount=0.04,
        seed=seed + 1,
    )

    # 3. Seven organic tea-leaf marbled crackle networks
    cracks_uv = [
        [(-0.72, -0.22), (-0.28, -0.08), (0.06, -0.32), (0.48, -0.52)],
        [(-0.28, -0.08), (-0.12, 0.28), (0.26, 0.46), (0.68, 0.25)],
        [(0.06, -0.32), (0.24, 0.04), (0.66, -0.06)],
        [(-0.64, 0.34), (-0.12, 0.28), (-0.32, 0.68)],
        [(0.24, 0.04), (0.02, 0.56), (0.28, 0.78)],
        [(-0.44, -0.62), (-0.08, -0.46), (0.06, -0.32)],
        [(0.26, 0.46), (0.52, 0.64)],
    ]
    for idx, chain in enumerate(cracks_uv):
        pts = [_egg_pt(u, v) for u, v in chain]
        cv.polyline(pts, color_key="crack", stroke_scale=0.52, seed=seed + 10 + idx)

    # 4. Crisp outer shell outline on top
    cv.polygon(
        contour,
        fill_key=None,
        outline_key="outline",
        stroke_scale=0.92,
        seed=seed,
    )


def draw_steam_plume(
    cv: StyleCanvas,
    cam: CameraState,
    wx: float,
    wy: float,
    t_sec: float,
    height_w: float = 115.0,
    sway_w: float = 13.0,
    puff_count: int = 7,
    base_radius_w: float = 13.0,
    seed: int = 300,
) -> None:
    """Gentle S-curve rising fragrant white steam wisps."""
    for i in range(puff_count):
        phase = (i / float(puff_count) + t_sec * 0.48) % 1.0
        py = wy - phase * height_w
        px = wx + math.sin(phase * math.pi * 2.2 + t_sec * 2.1 + i * 0.7) * sway_w * (0.35 + 0.65 * phase)
        env = math.sin(phase * math.pi)
        rad = cam.scale(base_radius_w * (0.55 + 0.75 * phase) * (0.45 + 0.55 * env))
        dens = 0.82 * env
        sx, sy = cam.project(px, py)
        cv.steam_puff(sx, sy, rad, density=dens, seed=seed + i)

    curl_pts: List[Point] = []
    for k in range(8):
        u = 0.12 + 0.72 * (k / 7.0)
        py = wy - u * height_w * 0.88
        px = wx + math.sin(u * math.pi * 2.4 - t_sec * 2.6) * (sway_w * 0.75)
        curl_pts.append(cam.project(px, py))
    cv.polyline(curl_pts, color_key="steam", stroke_scale=0.55, seed=seed + 99)


def draw_clerk_shot2(
    cv: StyleCanvas,
    cam: CameraState,
    frame_idx: int,
    t_sec: float,
    egg_world: Tuple[float, float],
) -> Tuple[float, float]:
    """Shot 2 [2.5s - 5.5s]: Clerk walks in from left, gazes at tea egg, reaches out,
    hesitates (visible pullback + blink), smiles warmly, and picks up the egg.
    """
    # 1) Walk in: 2.50s -> 3.40s (walks comfortably close to steamer so arm has natural bend!)
    u_walk = clamp((t_sec - 2.50) / 0.90)
    walk_ease = 1.0 - (1.0 - u_walk) ** 2.4
    clerk_x = lerp(110.0, 536.0, walk_ease)
    walk_bob = -abs(math.sin(u_walk * math.pi * 2.0)) * 8.5 * (1.0 - 0.60 * u_walk) if u_walk < 1.0 else 0.0
    breath_y = math.sin(t_sec * 2.6) * 2.0 if u_walk >= 1.0 else 0.0

    # 2) Reach toward steamer: 3.40s -> 4.10s
    u_reach = smoothstep((t_sec - 3.40) / 0.70)

    # 3) Hesitation pullback: 4.10s -> 4.72s (hand visibly pauses & draws back ~32px!)
    if t_sec < 4.10:
        hes_pull = 0.0
    elif t_sec < 4.72:
        hes_pull = math.sin(clamp((t_sec - 4.10) / 0.62) * math.pi * 0.86)
    else:
        hes_pull = math.sin(0.86 * math.pi) * (1.0 - smoothstep((t_sec - 4.72) / 0.30))

    # 4) Warm smile: 4.72s -> 5.50s
    u_smile = smoothstep((t_sec - 4.72) / 0.45)

    # 5) Confident reach in to pick up tea egg: 5.02s -> 5.48s
    u_grab = smoothstep((t_sec - 5.02) / 0.44)

    lean_x = 12.0 * u_reach - 6.0 * hes_pull + 16.0 * u_grab
    hx = clerk_x + lean_x
    hy = 278.0 + walk_bob + breath_y

    # Tea egg lifts slightly in final 0.24s as clerk picks it up
    u_lift = smoothstep((t_sec - 5.24) / 0.24)
    cur_egg_x = egg_world[0] - 8.0 * u_lift
    cur_egg_y = egg_world[1] - 18.0 * u_lift

    # Hand trajectory in world space (natural relaxed hip/waist swing during walk -> reach -> hesitate -> grab)
    walk_swing = math.sin(u_walk * math.pi * 2.0) * 12.0 * (1.0 - u_walk)
    rest_hand = (clerk_x + 56.0 + walk_swing, 494.0 + walk_bob * 0.6)
    reach_hand = (734.0, 438.0)  # Right at the open steamer threshold!
    hx_t = lerp(rest_hand[0], reach_hand[0], u_reach) - 32.0 * hes_pull
    hy_t = lerp(rest_hand[1], reach_hand[1], u_reach) - 12.0 * hes_pull
    grab_target = (cur_egg_x - 36.0, cur_egg_y + 2.0)
    hand_wx = lerp(hx_t, grab_target[0], u_grab)
    hand_wy = lerp(hy_t, grab_target[1], u_grab)

    def P(wx: float, wy: float) -> Point:
        return cam.project(wx, wy)

    S = cam.scale

    # --- 1. Back Cranium Hair Cap (STRICTLY behind head & high above face!) ---
    hcx, hcy = P(hx - 14.0, hy - 10.0)
    cv.ellipse(
        hcx,
        hcy,
        S(58.0),
        S(66.0),
        angle_deg=-10.0,
        fill_key="hair",
        outline_key="outline",
        stroke_scale=0.95,
        tooth_amount=0.12,
        seed=402,
    )

    # --- 2. Neck & Rounded 3/4 Torso (Cream Shirt + Convenience Store Green Apron) ---
    neck_pts = _capsule_points(*P(hx - 4.0, hy + 48.0), *P(hx - 2.0, hy + 96.0), S(19.0), S(21.0))
    cv.polygon(neck_pts, fill_key="skin", outline_key="outline", stroke_scale=0.85, tooth_amount=0.04, seed=403)

    # Natural sloped 3/4 shoulders & upper torso
    torso_world = [
        (hx - 26.0, hy + 88.0),
        (hx + 26.0, hy + 88.0),
        (hx + 46.0, hy + 114.0),
        (hx + 54.0, hy + 340.0),
        (hx - 54.0, hy + 340.0),
        (hx - 50.0, hy + 122.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in torso_world],
        fill_key="shirt",
        outline_key="outline",
        stroke_scale=0.95,
        tooth_amount=0.10,
        seed=404,
    )

    # Green clerk apron over shirt
    apron_world = [
        (hx - 36.0, hy + 126.0),
        (hx + 46.0, hy + 120.0),
        (hx + 54.0, hy + 340.0),
        (hx - 46.0, hy + 340.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in apron_world],
        fill_key="apron",
        outline_key="outline",
        stroke_scale=0.92,
        tooth_amount=0.15,
        shade_key="apron_dark",
        seed=405,
    )
    # Apron neck strap
    strap_world = [
        (hx - 12.0, hy + 88.0),
        (hx + 4.0, hy + 88.0),
        (hx + 28.0, hy + 124.0),
        (hx + 10.0, hy + 126.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in strap_world],
        fill_key="apron",
        outline_key="outline",
        stroke_scale=0.80,
        tooth_amount=0.12,
        seed=406,
    )
    # Decorative color stripe on apron (zero text)
    stripe_world = [
        (hx - 35.0, hy + 144.0),
        (hx + 45.0, hy + 139.0),
        (hx + 46.0, hy + 152.0),
        (hx - 36.0, hy + 157.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in stripe_world],
        fill_key="glow_inner",
        outline_key="outline",
        stroke_scale=0.65,
        tooth_amount=0.08,
        seed=407,
    )
    # Shirt collar lapel
    collar_world = [
        (hx - 20.0, hy + 84.0),
        (hx + 20.0, hy + 86.0),
        (hx + 12.0, hy + 108.0),
        (hx - 18.0, hy + 102.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in collar_world],
        fill_key="shirt",
        outline_key="outline",
        stroke_scale=0.80,
        tooth_amount=0.06,
        seed=408,
    )

    # --- 3. Clean 3/4 Face & High-Cropped Short Hair (ZERO hair occluding face, ZERO chin dither!) ---
    fcx, fcy = P(hx + 4.0, hy)
    cv.ellipse(
        fcx,
        fcy,
        S(54.0),
        S(60.0),
        angle_deg=4.0,
        fill_key="skin",
        outline_key="outline",
        stroke_scale=0.95,
        tooth_amount=0.03,
        shade_key=None,
        seed=410,
    )

    # Left ear
    ecx, ecy = P(hx - 44.0, hy + 6.0)
    cv.ellipse(
        ecx,
        ecy,
        S(13.0),
        S(17.0),
        angle_deg=-8.0,
        fill_key="skin",
        outline_key="outline",
        stroke_scale=0.82,
        tooth_amount=0.03,
        seed=411,
    )
    cv.arc_stroke(ecx, ecy, S(6.0), S(9.0), -70, 95, color_key="outline", stroke_scale=0.58, seed=412)

    # Top crown & neat high short bangs: STRICTLY y <= hy - 36 (18px clear skin above eyebrows!)
    top_hair_world = [
        (hx - 54.0, hy - 12.0),
        (hx - 56.0, hy - 44.0),
        (hx - 34.0, hy - 68.0),
        (hx + 4.0, hy - 72.0),
        (hx + 38.0, hy - 60.0),
        (hx + 52.0, hy - 42.0),
        (hx + 24.0, hy - 38.0),
        (hx - 8.0, hy - 40.0),
        (hx - 36.0, hy - 34.0),
        (hx - 44.0, hy - 10.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in top_hair_world],
        fill_key="hair",
        outline_key="outline",
        stroke_scale=0.92,
        tooth_amount=0.11,
        seed=413,
    )

    # --- 4. Facial Expression (Gaze at Tea Egg -> Hesitation Blink -> Smooth Warm Smile) ---
    is_blinking = (101 <= frame_idx <= 104) or (72 <= frame_idx <= 74)
    brow_lift = -4.5 * hes_pull - 2.5 * u_smile

    cv.polyline(
        [P(hx + 2.0, hy - 17.0 + brow_lift), P(hx + 14.0, hy - 20.5 + brow_lift), P(hx + 23.0, hy - 17.5 + brow_lift)],
        color_key="outline",
        stroke_scale=0.68,
        seed=414,
    )
    cv.polyline(
        [P(hx + 34.0, hy - 18.0 + brow_lift), P(hx + 44.0, hy - 20.5 + brow_lift), P(hx + 51.0, hy - 16.5 + brow_lift)],
        color_key="outline",
        stroke_scale=0.65,
        seed=415,
    )

    # Eyes gazing down-right at the steaming tea egg
    for idx_e, (ex_off, ey_off, erx, ery) in enumerate([(13.0, -2.0, 6.5, 8.2), (40.0, -2.0, 5.8, 7.6)]):
        ex_s, ey_s = P(hx + ex_off, hy + ey_off)
        if is_blinking:
            cv.arc_stroke(
                ex_s, ey_s + S(2.0), S(erx + 1.5), S(3.5), 15, 165, color_key="outline", stroke_scale=0.68, seed=416 + idx_e
            )
        else:
            cv.ellipse(
                ex_s + S(1.8),
                ey_s + S(1.8),
                S(erx),
                S(ery * (1.0 - 0.12 * u_smile)),
                fill_key="outline",
                outline_key=None,
                tooth_amount=0.02,
                seed=416 + idx_e,
            )
            cv.ellipse(
                ex_s + S(3.2),
                ey_s - S(1.2),
                S(2.3),
                S(2.3),
                fill_key="steam",
                outline_key=None,
                tooth_amount=0.0,
                seed=418 + idx_e,
            )

    # Cute 3/4 nose
    cv.polyline(
        [P(hx + 30.0, hy + 3.0), P(hx + 37.0, hy + 11.0), P(hx + 31.0, hy + 14.0)],
        color_key="outline",
        stroke_scale=0.62,
        seed=420,
    )

    # Rosy cheek blush placed cleanly on cheek (clear of mouth corner!)
    blush_r = lerp(8.5, 11.5, u_smile)
    bcx, bcy = P(hx + 2.0, hy + 16.0)
    cv.ellipse(bcx, bcy, S(blush_r), S(blush_r * 0.65), fill_key="blush", outline_key=None, tooth_amount=0.16, seed=421)

    # Smooth 6-point mouth curve: gentle neutral -> hesitant purse -> warm upward smile!
    corner_lift = 7.5 * u_smile - 1.2 * hes_pull
    belly_drop = 3.5 * u_smile
    m_pts: List[Point] = []
    for k in range(6):
        u_m = k / 5.0  # 0 (left cheek corner) -> 1 (right front of mouth)
        mx = hx + lerp(13.0, 35.0, u_m)
        # Parabolic smile arc with higher lift on left cheek corner!
        arch = 4.0 * u_m * (1.0 - u_m)
        my = hy + 30.0 - corner_lift * (1.0 - u_m) ** 1.3 - 2.0 * u_smile * (u_m ** 1.6) + belly_drop * arch
        m_pts.append(P(mx, my))
    cv.polyline(m_pts, color_key="outline", stroke_scale=0.72, seed=422)

    # --- 5. Foreground Right Arm + Rigid 5-Finger Hand Rig (Natural Soft Elbow Bend!) ---
    sh_w = (hx + 2.0, hy + 110.0)
    elbow_w, wrist_w = _solve_two_bone_ik(
        sh_w[0], sh_w[1], hand_wx, hand_wy, l1=106.0, l2=106.0, bend_down=True
    )

    # Forearm skin
    forearm_poly = _capsule_points(*P(*elbow_w), *P(*wrist_w), S(14.5), S(12.0))
    cv.polygon(forearm_poly, fill_key="skin", outline_key="outline", stroke_scale=0.88, tooth_amount=0.04, seed=424)

    # Upper arm + rolled shirt sleeve overlapping elbow cleanly
    sleeve_end = (lerp(sh_w[0], elbow_w[0], 0.96), lerp(sh_w[1], elbow_w[1], 0.96))
    sleeve_poly = _capsule_points(*P(*sh_w), *P(*sleeve_end), S(22.0), S(18.5))
    cv.polygon(sleeve_poly, fill_key="shirt", outline_key="outline", stroke_scale=0.90, tooth_amount=0.09, seed=425)

    # Rigid side-view 5-finger hand attached to wrist_w
    fore_ang = math.atan2(wrist_w[1] - elbow_w[1], wrist_w[0] - elbow_w[0])
    hand_ang = lerp(fore_ang * 0.45, -0.06, u_reach) - 0.18 * hes_pull
    ca_h, sa_h = math.cos(hand_ang), math.sin(hand_ang)

    def H(lx: float, ly: float) -> Point:
        return P(wrist_w[0] + lx * ca_h - ly * sa_h, wrist_w[1] + lx * sa_h + ly * ca_h)

    curl = 3.5 * hes_pull
    for f_idx, (fx1, fy0, fy1, fr) in enumerate(
        [
            (31.0 - curl, 8.5, 10.5, 4.3),   # pinky
            (36.0 - curl, 4.5, 6.0, 4.7),    # ring
            (40.0 - curl, 0.5, 1.5, 5.0),    # middle
        ]
    ):
        f_poly = _capsule_points(*H(14.0, fy0), *H(fx1, fy1), S(fr), S(fr * 0.88), steps_cap=6)
        cv.polygon(f_poly, fill_key="skin", outline_key="outline", stroke_scale=0.66, tooth_amount=0.04, seed=430 + f_idx)

    palm_poly = _capsule_points(*H(0.0, 1.0), *H(18.0, 1.0), S(13.0), S(12.5), steps_cap=7)
    cv.polygon(palm_poly, fill_key="skin", outline_key="outline", stroke_scale=0.78, tooth_amount=0.04, seed=434)

    idx_poly = _capsule_points(*H(15.0, -4.0), *H(43.0 - curl * 0.7, -4.5), S(5.2), S(4.6), steps_cap=6)
    cv.polygon(idx_poly, fill_key="skin", outline_key="outline", stroke_scale=0.70, tooth_amount=0.04, seed=435)

    thumb_ang_lift = -3.0 * hes_pull
    th_poly = _capsule_points(*H(8.0, -5.0), *H(26.0, -17.0 + thumb_ang_lift), S(5.8), S(5.0), steps_cap=6)
    cv.polygon(th_poly, fill_key="skin", outline_key="outline", stroke_scale=0.72, tooth_amount=0.04, seed=436)

    if u_grab > 0.55:
        cv.polyline([H(22.0, -6.0), P(cur_egg_x - 8.0, cur_egg_y - 6.0)], color_key="skewer", stroke_scale=0.82, seed=437)

    return cur_egg_x, cur_egg_y


def _shot3_mouth_openness(frame_idx: int) -> Tuple[float, float]:
    """Return (open_amount 0..1, width_factor 0.8..1.2) synced to Cantonese 7-syllable line:
    「最(135-140)・後(141-146)・一(147-151)・隻(152-158)，[pause]・係(164-169)・我(170-175)・嘅(176-182)。」
    """
    syllables = [
        (135, 140, 0.72, 0.86),  # 最
        (141, 146, 0.88, 1.02),  # 後
        (147, 151, 0.52, 1.16),  # 一
        (152, 158, 0.92, 1.08),  # 隻
        (164, 169, 0.84, 1.05),  # 係
        (170, 175, 0.78, 0.90),  # 我
        (176, 182, 0.95, 1.14),  # 嘅
    ]
    for f0, f1, peak_open, w_fac in syllables:
        if f0 <= frame_idx <= f1:
            u = (frame_idx - f0) / float(max(1, f1 - f0))
            return math.sin(u * math.pi) * peak_open, w_fac
    return 0.0, 1.08


def draw_clerk_shot3(cv: StyleCanvas, cam: CameraState, frame_idx: int, t_sec: float) -> None:
    """Shot 3 [5.5s - 8.0s]: Front MCU of clerk holding up the steaming tea egg in right hand
    (5 clean anatomical fingers around a small kraft paper cup + bamboo skewer) while speaking
    directly to the camera. Hair sits strictly high above eyebrows (zero face occlusion).
    """
    local_t = t_sec - 5.50
    breath_y = math.sin(local_t * 2.8) * 2.5
    egg_lift_intro = smoothstep(local_t / 0.32)
    hand_bob = math.sin(local_t * 3.2 + 0.4) * 3.0 - (1.0 - egg_lift_intro) * 26.0

    hx = 536.0
    hy = 296.0 + breath_y

    def P(wx: float, wy: float) -> Point:
        return cam.project(wx, wy)

    S = cam.scale

    cup_wx = 838.0
    cup_wy = 434.0 + hand_bob
    egg_wx = cup_wx
    egg_wy = cup_wy - 54.0

    # --- 1. Back Hair Silhouette (strictly behind head & ears) ---
    bhx, bhy = P(hx, hy - 14.0)
    cv.ellipse(
        bhx,
        bhy,
        S(102.0),
        S(100.0),
        fill_key="hair",
        outline_key="outline",
        stroke_scale=1.0,
        tooth_amount=0.12,
        seed=501,
    )

    # --- 2. Right Forearm (drawn before short shirt sleeve so sleeve cuff overlaps elbow seamlessly!) ---
    r_el = (744.0, 556.0 + hand_bob * 0.5)
    r_wr = (824.0, 468.0 + hand_bob)
    fore_poly = _capsule_points(*P(*r_el), *P(*r_wr), S(22.0), S(17.5))
    cv.polygon(fore_poly, fill_key="skin", outline_key="outline", stroke_scale=0.92, tooth_amount=0.04, seed=540)

    # --- 3. Neck + Unified Seamless Shirt Silhouette (Torso + Left Sleeve + Right Short Sleeve!) ---
    neck_poly = _capsule_points(*P(hx, hy + 68.0), *P(hx, hy + 132.0), S(27.0), S(30.0))
    cv.polygon(neck_poly, fill_key="skin", outline_key="outline", stroke_scale=0.90, tooth_amount=0.04, seed=502)

    eb_y = 260.0 + hand_bob * 0.5  # elbow offset relative to hy
    shirt_unified_world = [
        (hx - 40.0, hy + 120.0),
        (hx + 40.0, hy + 120.0),
        (hx + 114.0, hy + 126.0),
        (hx + 148.0, hy + 148.0),
        # Right short sleeve extending cleanly past right elbow!
        (768.0, hy + eb_y - 12.0),
        (728.0, hy + eb_y + 24.0),
        (hx + 122.0, hy + 216.0),
        (hx + 132.0, hy + 440.0),
        # Bottom across to left side & outer left sleeve
        (hx - 188.0, hy + 440.0),
        (hx - 176.0, hy + 188.0),
        (hx - 154.0, hy + 146.0),
        (hx - 114.0, hy + 126.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in shirt_unified_world],
        fill_key="shirt",
        outline_key="outline",
        stroke_scale=1.0,
        tooth_amount=0.10,
        seed=503,
    )
    # Subtle inner left-arm crease line so left sleeve reads clearly from torso
    cv.polyline(
        [P(hx - 124.0, hy + 206.0), P(hx - 132.0, hy + 436.0)],
        color_key="outline",
        stroke_scale=0.85,
        seed=5031,
    )

    # Apron straps & bib
    for side in (-1.0, 1.0):
        strap = [
            P(hx + side * 46.0, hy + 124.0),
            P(hx + side * 74.0, hy + 124.0),
            P(hx + side * 86.0, hy + 195.0),
            P(hx + side * 54.0, hy + 195.0),
        ]
        cv.polygon(
            strap, fill_key="apron", outline_key="outline", stroke_scale=0.88, tooth_amount=0.13, seed=504 + int(side > 0)
        )

    bib_pts = [
        P(hx - 96.0, hy + 186.0),
        P(hx + 96.0, hy + 186.0),
        P(hx + 112.0, hy + 440.0),
        P(hx - 112.0, hy + 440.0),
    ]
    cv.polygon(
        bib_pts,
        fill_key="apron",
        outline_key="outline",
        stroke_scale=0.96,
        tooth_amount=0.15,
        shade_key="apron_dark",
        seed=506,
    )
    band_pts = [
        P(hx - 95.0, hy + 206.0),
        P(hx + 95.0, hy + 206.0),
        P(hx + 97.0, hy + 224.0),
        P(hx - 97.0, hy + 224.0),
    ]
    cv.polygon(band_pts, fill_key="glow_inner", outline_key="outline", stroke_scale=0.72, tooth_amount=0.08, seed=507)

    # Crisp shirt V-collar lapels
    collar_l = [P(hx - 46.0, hy + 116.0), P(hx, hy + 156.0), P(hx - 28.0, hy + 166.0), P(hx - 62.0, hy + 132.0)]
    collar_r = [P(hx + 46.0, hy + 116.0), P(hx, hy + 156.0), P(hx + 28.0, hy + 166.0), P(hx + 62.0, hy + 132.0)]
    cv.polygon(collar_l, fill_key="shirt", outline_key="outline", stroke_scale=0.85, tooth_amount=0.06, seed=508)
    cv.polygon(collar_r, fill_key="shirt", outline_key="outline", stroke_scale=0.85, tooth_amount=0.06, seed=509)

    # --- 4. Ears & Clean Front Face Oval (shade_key=None so zero Pixel chin dither!) ---
    for side in (-1.0, 1.0):
        ex_e, ey_e = P(hx + side * 88.0, hy + 8.0)
        cv.ellipse(
            ex_e,
            ey_e,
            S(18.0),
            S(24.0),
            angle_deg=side * 8.0,
            fill_key="skin",
            outline_key="outline",
            stroke_scale=0.88,
            tooth_amount=0.03,
            seed=511 + int(side > 0),
        )
        cv.arc_stroke(
            ex_e,
            ey_e,
            S(8.0),
            S(12.0),
            -60 if side > 0 else 120,
            60 if side > 0 else 240,
            color_key="outline",
            stroke_scale=0.58,
            seed=513 + int(side > 0),
        )

    fcx, fcy = P(hx, hy)
    cv.ellipse(
        fcx,
        fcy,
        S(88.0),
        S(94.0),
        fill_key="skin",
        outline_key="outline",
        stroke_scale=1.0,
        tooth_amount=0.03,
        shade_key=None,
        seed=515,
    )

    # --- 5. Neat High-Cropped Cap Hair (STRICTLY y <= hy - 54 -> 24px clear forehead above brows!) ---
    crown_hair_world = [
        (hx - 92.0, hy - 18.0),
        (hx - 96.0, hy - 58.0),
        (hx - 74.0, hy - 94.0),
        (hx - 32.0, hy - 112.0),
        (hx + 24.0, hy - 112.0),
        (hx + 72.0, hy - 94.0),
        (hx + 96.0, hy - 58.0),
        (hx + 92.0, hy - 18.0),
        (hx + 80.0, hy - 48.0),
        (hx + 52.0, hy - 58.0),
        (hx + 14.0, hy - 62.0),
        (hx - 18.0, hy - 56.0),
        (hx - 54.0, hy - 58.0),
        (hx - 80.0, hy - 48.0),
    ]
    cv.polygon(
        [P(x, y) for x, y in crown_hair_world],
        fill_key="hair",
        outline_key="outline",
        stroke_scale=0.96,
        tooth_amount=0.11,
        seed=516,
    )

    # --- 6. Expressive Front Eyes, Brows, Blush & Lip-Synced Mouth ---
    open_amt, width_fac = _shot3_mouth_openness(frame_idx)
    is_blinking = 160 <= frame_idx <= 162
    brow_bob = -3.0 * open_amt - 2.0

    cv.polyline(
        [P(hx - 52.0, hy - 26.0 + brow_bob), P(hx - 35.0, hy - 32.0 + brow_bob), P(hx - 18.0, hy - 28.0 + brow_bob)],
        color_key="outline",
        stroke_scale=0.74,
        seed=517,
    )
    cv.polyline(
        [P(hx + 18.0, hy - 28.0 + brow_bob), P(hx + 35.0, hy - 32.0 + brow_bob), P(hx + 52.0, hy - 26.0 + brow_bob)],
        color_key="outline",
        stroke_scale=0.74,
        seed=518,
    )

    for side in (-1.0, 1.0):
        ex_c, ey_c = P(hx + side * 35.0, hy - 6.0)
        if is_blinking:
            cv.arc_stroke(
                ex_c, ey_c + S(2.0), S(12.5), S(5.5), 15, 165, color_key="outline", stroke_scale=0.76, seed=520 + int(side > 0)
            )
        else:
            cv.ellipse(
                ex_c,
                ey_c,
                S(10.5),
                S(13.0),
                fill_key="outline",
                outline_key=None,
                tooth_amount=0.02,
                seed=520 + int(side > 0),
            )
            cv.arc_stroke(
                ex_c, ey_c - S(1.0), S(13.5), S(12.0), 200, 340, color_key="outline", stroke_scale=0.68, seed=522 + int(side > 0)
            )
            cv.ellipse(
                ex_c + S(3.5),
                ey_c - S(4.2),
                S(3.4),
                S(3.4),
                fill_key="steam",
                outline_key=None,
                tooth_amount=0.0,
                seed=524 + int(side > 0),
            )

    for side in (-1.0, 1.0):
        bx_c, by_c = P(hx + side * 54.0, hy + 19.0)
        cv.ellipse(bx_c, by_c, S(16.0), S(10.5), fill_key="blush", outline_key=None, tooth_amount=0.16, seed=526 + int(side > 0))

    cv.polyline(
        [P(hx - 2.0, hy + 6.0), P(hx + 3.0, hy + 15.0), P(hx - 3.0, hy + 17.0)],
        color_key="outline",
        stroke_scale=0.65,
        seed=528,
    )

    mw = 24.0 * width_fac
    my = hy + 38.0
    if open_amt > 0.12:
        mh = 5.0 + 16.0 * open_amt
        mouth_pts = [
            P(hx - mw, my - 3.0),
            P(hx, my - 1.0),
            P(hx + mw, my - 3.0),
            P(hx + mw * 0.78, my + mh * 0.72),
            P(hx, my + mh),
            P(hx - mw * 0.78, my + mh * 0.72),
        ]
        cv.polygon(mouth_pts, fill_key="mouth_in", outline_key=None, tooth_amount=0.04, seed=530)
        tx_c, ty_c = P(hx, my + mh * 0.68)
        cv.ellipse(tx_c, ty_c, S(mw * 0.48), S(mh * 0.32), fill_key="tongue", outline_key=None, tooth_amount=0.04, seed=531)
        cv.polygon(mouth_pts, fill_key=None, outline_key="outline", stroke_scale=0.76, seed=530)
    else:
        smile_pts = [
            P(hx - 25.0, my - 4.0),
            P(hx - 12.0, my + 6.0),
            P(hx, my + 8.0),
            P(hx + 12.0, my + 6.0),
            P(hx + 25.0, my - 4.0),
        ]
        cv.polyline(smile_pts, color_key="outline", stroke_scale=0.82, seed=532)

    # --- 7. Kraft Paper Cup, Steaming Tea Egg & Explicit 5-Finger Hand ---
    palm_cx, palm_cy = P(cup_wx + 6.0, cup_wy + 12.0)
    cv.ellipse(palm_cx, palm_cy, S(34.0), S(28.0), fill_key="skin", outline_key="outline", stroke_scale=0.82, tooth_amount=0.04, seed=542)

    cv.polyline(
        [P(egg_wx + 12.0, egg_wy - 48.0), P(egg_wx + 4.0, egg_wy - 22.0)],
        color_key="skewer",
        stroke_scale=0.95,
        seed=543,
    )

    draw_steam_plume(
        cv,
        cam,
        egg_wx,
        egg_wy - 40.0,
        t_sec=t_sec,
        height_w=135.0,
        sway_w=14.0,
        puff_count=7,
        base_radius_w=14.5,
        seed=544,
    )

    draw_tea_egg(cv, cam, egg_wx, egg_wy, scale=1.68, tilt_deg=-5.0, seed=545)

    cup_pts = [
        P(cup_wx - 44.0, cup_wy - 28.0),
        P(cup_wx + 44.0, cup_wy - 28.0),
        P(cup_wx + 32.0, cup_wy + 38.0),
        P(cup_wx - 32.0, cup_wy + 38.0),
    ]
    cv.polygon(
        cup_pts,
        fill_key="cup",
        outline_key="outline",
        stroke_scale=0.90,
        tooth_amount=0.10,
        shade_key="counter",
        seed=546,
    )
    cup_band = [
        P(cup_wx - 39.0, cup_wy - 4.0),
        P(cup_wx + 39.0, cup_wy - 4.0),
        P(cup_wx + 36.0, cup_wy + 10.0),
        P(cup_wx - 36.0, cup_wy + 10.0),
    ]
    cv.polygon(cup_band, fill_key="cup_stripe", outline_key="outline", stroke_scale=0.62, tooth_amount=0.08, seed=547)

    # Finger #1: Opposable Thumb cleanly hugging left side of cup
    thumb_poly = _capsule_points(
        *P(cup_wx - 54.0, cup_wy + 8.0),
        *P(cup_wx - 28.0, cup_wy - 2.0),
        S(10.0),
        S(9.0),
        steps_cap=7,
    )
    cv.polygon(thumb_poly, fill_key="skin", outline_key="outline", stroke_scale=0.78, tooth_amount=0.04, seed=551)

    # Fingers #2..#5: Index, Middle, Ring, Pinky cleanly stacked on right side of cup
    finger_specs = [
        (48.0, -14.0, 8.2),  # Index (#2)
        (50.0, 2.0, 8.4),    # Middle (#3)
        (47.0, 18.0, 7.9),   # Ring (#4)
        (42.0, 32.0, 7.2),   # Pinky (#5)
    ]
    for idx_f, (x_out, y_off, rad_f) in enumerate(finger_specs):
        x_in = 20.0 - idx_f * 1.2
        f_poly = _capsule_points(
            *P(cup_wx + x_in, cup_wy + y_off),
            *P(cup_wx + x_out, cup_wy + y_off + 2.0),
            S(rad_f * 0.92),
            S(rad_f),
            steps_cap=7,
        )
        cv.polygon(
            f_poly,
            fill_key="skin",
            outline_key="outline",
            stroke_scale=0.76,
            tooth_amount=0.04,
            seed=552 + idx_f,
        )
