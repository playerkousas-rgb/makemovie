"""Unified 3-Shot Scene Graph for Treatment 1:
- Shot 1 [0.0-2.5s | Frames 000-059]: Empty midnight convenience store, slow dolly-in to last steaming tea egg.
- Shot 2 [2.5-5.5s | Frames 060-131]: Clerk enters from left, gazes at egg, reaches, hesitates, smiles, picks it up.
- Shot 3 [5.5-8.0s | Frames 132-191]: Front MCU holding steaming tea egg, speaking to camera.

100% shared coordinates across Version A (crayon) and Version B (pixel).
Zero text drawn inside scene geometry (all Chinese text is strictly added in subtitle.py).
"""

from __future__ import annotations

import math

from PIL import Image

from camera import CameraState, get_camera_state
from character import draw_clerk_shot2, draw_clerk_shot3, draw_steam_plume, draw_tea_egg
from spec_loader import SpecConfig
from style_backends import StyleCanvas, make_canvas


def _draw_konbini_stripes(cv: StyleCanvas, cam: CameraState, y_top: float = 18.0, band_h: float = 13.0) -> None:
    """Iconic 3-band convenience store ceiling trim (green, amber, coral) — zero text!"""
    for idx, ckey in enumerate(("shelf", "glow", "accent_coral")):
        y0 = y_top + idx * band_h
        y1 = y0 + band_h
        pts = [
            cam.project(-80.0, y0),
            cam.project(1360.0, y0),
            cam.project(1360.0, y1),
            cam.project(-80.0, y1),
        ]
        cv.polygon(pts, fill_key=ckey, outline_key=None, tooth_amount=0.14, seed=10 + idx)
    cv.polyline(
        [cam.project(-80.0, y_top + 3 * band_h), cam.project(1360.0, y_top + 3 * band_h)],
        color_key="outline",
        stroke_scale=0.80,
        seed=14,
    )


def _draw_night_window(
    cv: StyleCanvas,
    cam: CameraState,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    t_sec: float,
    show_moon: bool = True,
    seed: int = 30,
) -> None:
    """Midnight window looking out onto dark indigo sky, quiet city silhouettes, crescent moon & stars."""
    P = cam.project
    S = cam.scale

    win_pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
    cv.polygon(win_pts, fill_key="night", outline_key="outline", stroke_scale=1.0, tooth_amount=0.12, shade_key="night_mid", seed=seed)

    w_span = x1 - x0
    bldg_specs = [
        (0.04, 0.24, 0.42),
        (0.22, 0.46, 0.54),
        (0.45, 0.68, 0.36),
        (0.66, 0.94, 0.48),
    ]
    for bi, (u0, u1, h_frac) in enumerate(bldg_specs):
        bx0 = x0 + w_span * u0
        bx1 = x0 + w_span * u1
        by0 = y1 - (y1 - y0) * h_frac
        bpts = [P(bx0, by0), P(bx1, by0), P(bx1, y1), P(bx0, y1)]
        cv.polygon(bpts, fill_key="night_mid", outline_key=None, tooth_amount=0.12, seed=seed + 2 + bi)

    for wi, (ux, uy) in enumerate([(0.30, 0.62), (0.36, 0.72), (0.76, 0.66)]):
        wx = x0 + w_span * ux
        wy = y0 + (y1 - y0) * uy
        if x0 + 18 < wx < x1 - 18 and y0 + 18 < wy < y1 - 18:
            w_rect = [P(wx - 7, wy - 9), P(wx + 7, wy - 9), P(wx + 7, wy + 9), P(wx - 7, wy + 9)]
            cv.polygon(w_rect, fill_key="moon", outline_key=None, tooth_amount=0.06, seed=seed + 10 + wi)

    if show_moon and w_span > 180.0:
        mcx, mcy = P(x0 + w_span * 0.76, y0 + (y1 - y0) * 0.25)
        cv.ellipse(mcx, mcy, S(24.0), S(24.0), fill_key="moon", outline_key=None, tooth_amount=0.06, seed=seed + 20)
        cv.ellipse(
            mcx - S(8.5),
            mcy - S(4.0),
            S(20.0),
            S(20.0),
            fill_key="night",
            outline_key=None,
            tooth_amount=0.06,
            seed=seed + 21,
        )

    star_uv = [(0.16, 0.22), (0.34, 0.16), (0.54, 0.28), (0.88, 0.40)]
    for si, (ux, uy) in enumerate(star_uv):
        twinkle = 0.75 + 0.25 * math.sin(t_sec * 3.1 + si * 1.7)
        sx, sy = P(x0 + w_span * ux, y0 + (y1 - y0) * uy)
        r_st = S(3.2 * twinkle)
        cv.ellipse(sx, sy, r_st, r_st, fill_key="moon", outline_key=None, tooth_amount=0.0, seed=seed + 30 + si)

    mid_x = x0 + w_span * 0.52
    cv.polyline([P(mid_x, y0), P(mid_x, y1)], color_key="steamer_dark", stroke_scale=0.80, seed=seed + 40)
    cv.polyline([P(x0 + 28, y0 + 52), P(x0 + 68, y0 + 18)], color_key="glass_tint", stroke_scale=0.65, seed=seed + 41)
    cv.polyline([P(x0 + 42, y0 + 78), P(x0 + 92, y0 + 34)], color_key="glass_tint", stroke_scale=0.50, seed=seed + 42)
    cv.polygon(win_pts, fill_key=None, outline_key="outline", stroke_scale=1.0, seed=seed)


def _draw_store_shelf_unit(
    cv: StyleCanvas, cam: CameraState, x0: float, y0: float, x1: float, y1: float, seed: int = 80
) -> None:
    """Geometric convenience-store snack & drink shelf (strictly zero text/numbers!)."""
    P = cam.project
    back = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
    cv.polygon(back, fill_key="wall_shade", outline_key="outline", stroke_scale=0.90, tooth_amount=0.14, seed=seed)

    h = y1 - y0
    shelf_ys = [y0 + h * 0.46, y0 + h * 0.88]
    for si, sy in enumerate(shelf_ys):
        ledge = [P(x0 + 4, sy - 8), P(x1 - 4, sy - 8), P(x1 - 4, sy + 4), P(x0 + 4, sy + 4)]
        cv.polygon(ledge, fill_key="shelf", outline_key="outline", stroke_scale=0.72, tooth_amount=0.12, seed=seed + 2 + si)

    w = x1 - x0
    items_top = [
        (0.08, 0.21, 0.24, "accent_coral"),
        (0.24, 0.37, 0.20, "glow_inner"),
        (0.42, 0.56, 0.23, "shelf"),
        (0.62, 0.75, 0.22, "accent_berry"),
        (0.79, 0.91, 0.25, "glow"),
    ]
    for ii, (u0, u1, top_f, ckey) in enumerate(items_top):
        ix0, ix1 = x0 + w * u0, x0 + w * u1
        iy1 = shelf_ys[0] - 8
        iy0 = y0 + h * top_f
        box = [P(ix0, iy0), P(ix1, iy0), P(ix1, iy1), P(ix0, iy1)]
        cv.polygon(box, fill_key=ckey, outline_key="outline", stroke_scale=0.62, tooth_amount=0.12, seed=seed + 10 + ii)

    for bi in range(5):
        bx = x0 + w * (0.14 + bi * 0.175)
        by1 = shelf_ys[1] - 8
        by0 = shelf_ys[0] + 16
        ckey = ("shelf", "accent_coral", "glow_inner", "accent_berry", "shelf")[bi]
        bpoly = [
            P(bx - 12, by0 + 8),
            P(bx - 6, by0),
            P(bx + 6, by0),
            P(bx + 12, by0 + 8),
            P(bx + 12, by1),
            P(bx - 12, by1),
        ]
        cv.polygon(bpoly, fill_key=ckey, outline_key="outline", stroke_scale=0.60, tooth_amount=0.12, seed=seed + 25 + bi)


def _draw_steamer_shot1(cv: StyleCanvas, cam: CameraState, t_sec: float) -> None:
    """Glass countertop tea-egg steamer in Shot 1: 3x3 tray in shallow tea broth, ONLY 1 tea egg left!"""
    P = cam.project
    S = cam.scale

    cx = 835.0
    # Transparent glass cabinet interior (warm golden-lit air)
    glass_back = [P(cx - 135, 274), P(cx + 135, 274), P(cx + 145, 456), P(cx - 145, 456)]
    cv.polygon(glass_back, fill_key="glow_inner", outline_key="outline", stroke_scale=0.92, tooth_amount=0.14, seed=201)

    # Perspective 3x3 stainless broth tray inside steamer
    tray_outer = [P(cx - 122, 386), P(cx + 122, 386), P(cx + 136, 454), P(cx - 136, 454)]
    cv.polygon(
        tray_outer, fill_key="broth", outline_key="outline", stroke_scale=0.82, tooth_amount=0.10, shade_key="crack", seed=202
    )

    for rx_off, ry_off in [(-78, 405), (0, 402), (78, 405), (-84, 434), (84, 434)]:
        bsx, bsy = P(cx + rx_off, ry_off)
        cv.ellipse(bsx, bsy, S(22.0), S(6.5), fill_key="broth_light", outline_key=None, tooth_amount=0.15, seed=203)

    for u in (-0.34, 0.34):
        cv.polyline(
            [P(cx + 120 * u, 387), P(cx + 134 * u, 453)],
            color_key="steamer",
            stroke_scale=0.66,
            seed=205 + int(u > 0),
        )
    for v in (0.34, 0.68):
        wy_g = 386.0 + (454.0 - 386.0) * v
        w_half = 122.0 + 14.0 * v
        cv.polyline([P(cx - w_half, wy_g), P(cx + w_half, wy_g)], color_key="steamer", stroke_scale=0.64, seed=208 + int(v * 10))

    # THE LAST TEA EGG sitting in front-center compartment + rising S-curve steam!
    simmer_bob = math.sin(t_sec * 3.4) * 1.4
    egg_wx = cx + 2.0
    egg_wy = 414.0 + simmer_bob

    erx, ery = P(egg_wx, egg_wy + 24.0)
    cv.ellipse(erx, ery, S(34.0), S(9.0), fill_key="glow", outline_key=None, tooth_amount=0.18, seed=212)

    draw_tea_egg(cv, cam, egg_wx, egg_wy, scale=1.18, tilt_deg=4.0, seed=215)

    draw_steam_plume(
        cv,
        cam,
        egg_wx,
        egg_wy - 34.0,
        t_sec=t_sec,
        height_w=105.0,
        sway_w=11.0,
        puff_count=6,
        base_radius_w=11.5,
        seed=220,
    )

    base_pts = [P(cx - 150, 454), P(cx + 150, 454), P(cx + 156, 494), P(cx - 156, 494)]
    cv.polygon(
        base_pts, fill_key="steamer", outline_key="outline", stroke_scale=0.95, tooth_amount=0.11, shade_key="steamer_dark", seed=225
    )
    px_l, py_l = P(cx - 112, 474)
    cv.ellipse(px_l, py_l, S(6.5), S(6.5), fill_key="accent_coral", outline_key="outline", stroke_scale=0.58, tooth_amount=0.04, seed=226)
    px_dial, py_dial = P(cx + 108, 474)
    cv.ellipse(px_dial, py_dial, S(9.5), S(9.5), fill_key="steamer_dark", outline_key="outline", stroke_scale=0.62, tooth_amount=0.06, seed=227)

    hood_pts = [P(cx - 142, 250), P(cx + 142, 250), P(cx + 140, 276), P(cx - 140, 276)]
    cv.polygon(
        hood_pts, fill_key="steamer", outline_key="outline", stroke_scale=0.95, tooth_amount=0.11, shade_key="steamer_dark", seed=228
    )

    draw_steam_plume(
        cv,
        cam,
        cx + 8.0,
        246.0,
        t_sec=t_sec + 0.7,
        height_w=92.0,
        sway_w=15.0,
        puff_count=5,
        base_radius_w=13.0,
        seed=230,
    )

    cv.polyline([P(cx - 122, 334), P(cx - 92, 290)], color_key="steam", stroke_scale=0.62, seed=235)
    cv.polyline([P(cx + 98, 356), P(cx + 124, 316)], color_key="steam", stroke_scale=0.58, seed=236)
    cv.polygon(glass_back, fill_key=None, outline_key="outline", stroke_scale=0.95, seed=201)


def render_shot1(cv: StyleCanvas, cam: CameraState) -> None:
    """Shot 1 [0.0s - 2.5s]: Empty late-night convenience store, slow dolly-in onto steamer."""
    P = cam.project
    S = cam.scale
    t = cam.time_sec

    cv.fill_background("wall", shade_key="wall_shade")
    # Paint warm discrete light halo onto the wall BEFORE foreground props so outlines stay crisp!
    gx, gy = P(835.0, 380.0)
    cv.light_glow_rings(
        gx,
        gy,
        radii=[S(260.0), S(190.0), S(130.0)],
        color_keys=["glow_outer", "glow", "glow_inner"],
        densities=[0.38, 0.58, 0.78],
    )

    _draw_konbini_stripes(cv, cam, y_top=16.0, band_h=14.0)
    _draw_night_window(cv, cam, 68.0, 92.0, 585.0, 420.0, t_sec=t, show_moon=True, seed=30)
    _draw_store_shelf_unit(cv, cam, 92.0, 268.0, 448.0, 480.0, seed=80)

    # Cozy hanging pendant lamp above steamer counter
    cv.polyline([P(835, 58), P(835, 132)], color_key="outline", stroke_scale=0.82, seed=180)
    lamp_shade = [P(790, 158), P(812, 128), P(858, 128), P(880, 158)]
    cv.polygon(lamp_shade, fill_key="shelf_dark", outline_key="outline", stroke_scale=0.88, tooth_amount=0.12, seed=181)

    # Foreground wooden counter spanning across store (with diagonal crayon wood streaks!)
    counter_top = [P(-80, 482), P(1360, 482), P(1360, 520), P(-80, 520)]
    counter_front = [P(-80, 520), P(1360, 520), P(1360, 760), P(-80, 760)]
    cv.polygon(counter_front, fill_key="counter_dark", outline_key=None, tooth_amount=0.18, shade_key="counter", seed=190)
    cv.polygon(counter_top, fill_key="counter", outline_key="outline", stroke_scale=0.98, tooth_amount=0.15, shade_key="counter_dark", seed=191)

    # Warm bounce-light ellipse on wooden counter beneath steamer
    bx_l, by_l = P(835.0, 501.0)
    cv.ellipse(bx_l, by_l, S(188.0), S(14.0), fill_key="glow_outer", outline_key=None, tooth_amount=0.20, seed=192)

    # Unattended retro cash register on left counter
    reg_base = [P(205, 448), P(345, 448), P(352, 488), P(198, 488)]
    reg_body = [P(218, 392), P(326, 392), P(338, 448), P(210, 448)]
    reg_disp = [P(242, 362), P(306, 362), P(306, 392), P(242, 392)]
    cv.polygon(reg_base, fill_key="steamer_dark", outline_key="outline", stroke_scale=0.88, tooth_amount=0.11, seed=194)
    cv.polygon(reg_body, fill_key="steamer", outline_key="outline", stroke_scale=0.88, tooth_amount=0.11, seed=195)
    cv.polygon(reg_disp, fill_key="shelf_dark", outline_key="outline", stroke_scale=0.80, tooth_amount=0.10, seed=196)
    for kb in range(3):
        kx, ky = P(244 + kb * 24, 424)
        cv.ellipse(kx, ky, S(6.5), S(5.0), fill_key="glow_inner", outline_key="outline", stroke_scale=0.52, seed=197 + kb)

    _draw_steamer_shot1(cv, cam, t_sec=t)


def render_shot2(cv: StyleCanvas, cam: CameraState) -> None:
    """Shot 2 [2.5s - 5.5s]: Side medium-close two-shot. Clerk walks in, eyes the tea egg,
    reaches out, hesitates, smiles warmly, and picks up the egg.
    """
    P = cam.project
    S = cam.scale
    t = cam.time_sec

    st_cx = 852.0
    egg_base_world = (840.0, 446.0)

    cv.fill_background("wall", shade_key="wall_shade")
    # Paint warm steamer light halo onto wall first so window & steamer outlines remain crisp!
    gx, gy = P(st_cx - 12.0, 425.0)
    cv.light_glow_rings(
        gx,
        gy,
        radii=[S(295.0), S(210.0), S(140.0)],
        color_keys=["glow_outer", "glow", "glow_inner"],
        densities=[0.36, 0.56, 0.78],
    )

    _draw_konbini_stripes(cv, cam, y_top=12.0, band_h=15.0)
    _draw_night_window(cv, cam, 48.0, 88.0, 468.0, 438.0, t_sec=t, show_moon=True, seed=601)

    # Steamer back glass wall + lifted hinged glass lid (open toward clerk on left!)
    back_glass = [P(st_cx - 134, 336), P(st_cx + 134, 336), P(st_cx + 144, 492), P(st_cx - 144, 492)]
    cv.polygon(back_glass, fill_key="glow_inner", outline_key="outline", stroke_scale=0.90, tooth_amount=0.14, seed=610)

    open_lid = [P(st_cx + 132, 336), P(st_cx - 42, 232), P(st_cx - 28, 218), P(st_cx + 142, 322)]
    cv.polygon(open_lid, fill_key="glass_tint", outline_key="outline", stroke_scale=0.85, tooth_amount=0.10, seed=611)

    tray_pts = [P(st_cx - 128, 430), P(st_cx + 128, 430), P(st_cx + 140, 490), P(st_cx - 140, 490)]
    cv.polygon(
        tray_pts, fill_key="broth", outline_key="outline", stroke_scale=0.84, tooth_amount=0.10, shade_key="crack", seed=612
    )
    for u in (-0.34, 0.34):
        cv.polyline(
            [P(st_cx + 124 * u, 432), P(st_cx + 136 * u, 488)], color_key="steamer", stroke_scale=0.65, seed=613 + int(u > 0)
        )

    # Clerk walks in behind counter, reaches right hand toward the open steamer tray!
    cur_egg_x, cur_egg_y = draw_clerk_shot2(
        cv, cam, frame_idx=cam.frame_idx, t_sec=t, egg_world=egg_base_world
    )

    draw_tea_egg(cv, cam, cur_egg_x, cur_egg_y, scale=1.32, tilt_deg=-4.0, seed=620)
    draw_steam_plume(
        cv,
        cam,
        cur_egg_x,
        cur_egg_y - 38.0,
        t_sec=t,
        height_w=125.0,
        sway_w=13.0,
        puff_count=7,
        base_radius_w=13.0,
        seed=625,
    )

    st_base = [P(st_cx - 152, 488), P(st_cx + 152, 488), P(st_cx + 158, 540), P(st_cx - 158, 540)]
    cv.polygon(
        st_base, fill_key="steamer", outline_key="outline", stroke_scale=0.95, tooth_amount=0.11, shade_key="steamer_dark", seed=630
    )
    plx, ply = P(st_cx - 114, 514)
    cv.ellipse(plx, ply, S(7.0), S(7.0), fill_key="accent_coral", outline_key="outline", stroke_scale=0.58, seed=631)

    c_top = [P(-80, 538), P(1360, 538), P(1360, 578), P(-80, 578)]
    c_front = [P(-80, 578), P(1360, 578), P(1360, 760), P(-80, 760)]
    cv.polygon(c_front, fill_key="counter_dark", outline_key=None, tooth_amount=0.18, shade_key="counter", seed=635)
    cv.polygon(c_top, fill_key="counter", outline_key="outline", stroke_scale=0.98, tooth_amount=0.15, shade_key="counter_dark", seed=636)


def render_shot3(cv: StyleCanvas, cam: CameraState) -> None:
    """Shot 3 [5.5s - 8.0s]: Front MCU of clerk holding up the steaming tea egg
    and speaking directly to camera (subtitle added in post-process subtitle.py).
    """
    P = cam.project
    S = cam.scale
    t = cam.time_sec

    cv.fill_background("wall", shade_key="wall_shade")
    # Warm celebratory glow halo painted onto wall first so shelf & window outlines stay crisp!
    gx, gy = P(725.0, 385.0)
    cv.light_glow_rings(
        gx,
        gy,
        radii=[S(345.0), S(240.0), S(150.0)],
        color_keys=["glow_outer", "glow", "glow_inner"],
        densities=[0.36, 0.56, 0.76],
    )

    _draw_konbini_stripes(cv, cam, y_top=10.0, band_h=16.0)
    _draw_night_window(cv, cam, -20.0, 86.0, 252.0, 490.0, t_sec=t, show_moon=False, seed=701)

    # Cozy store shelf block on far right background with colorful geometric items (zero text!)
    _draw_store_shelf_unit(cv, cam, 1028.0, 162.0, 1306.0, 492.0, seed=705)

    # Hero Clerk + 5-Finger Hand + Paper Cup + Steaming Tea Egg!
    draw_clerk_shot3(cv, cam, frame_idx=cam.frame_idx, t_sec=t)

    # Foreground dark wooden counter ledge along bottom
    fg_ledge = [P(-80, 676), P(1360, 676), P(1360, 760), P(-80, 760)]
    cv.polygon(
        fg_ledge, fill_key="counter_dark", outline_key="outline", stroke_scale=0.92, tooth_amount=0.16, shade_key="counter", seed=720
    )


def render_clean_frame(frame_idx: int, style: str, cfg: SpecConfig) -> Image.Image:
    """Render one clean textless animation frame (0..191) in the requested style."""
    cam = get_camera_state(frame_idx, cfg)
    cv = make_canvas(style, cfg, frame_idx)
    if cam.shot_id == 1:
        render_shot1(cv, cam)
    elif cam.shot_id == 2:
        render_shot2(cv, cam)
    else:
        render_shot3(cv, cam)
    return cv.finalize()
