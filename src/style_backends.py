"""Dual procedural rendering engines:
- CrayonCanvas (Version A): Warm children's picture-book wax crayon on cotton paper
- PixelCanvas  (Version B): Crisp 16-bit retro console pixel art (320x180 -> 4x NEAREST)

Both share the exact same StyleCanvas interface and screen-space geometry.
Strict rules enforced:
- ZERO #000000 pure black anywhere
- ZERO smooth linear/radial gradients (only dry-crayon tooth/hatching or 4x4 Bayer dithering)
- 100% palette-locked colors from specs/01-color
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter

from spec_loader import SpecConfig

Point = Tuple[float, float]
RGB = Tuple[int, int, int]

# Classic 4x4 Bayer matrix normalized to [0, 1)
BAYER_4X4 = (
    np.array(
        [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ],
        dtype=np.float32,
    )
    + 0.5
) / 16.0


def _subdivide_polyline(pts: Sequence[Point], max_seg: float = 10.0, closed: bool = False) -> List[Point]:
    if len(pts) < 2:
        return list(pts)
    out: List[Point] = []
    n = len(pts)
    count = n if closed else n - 1
    for i in range(count):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(math.ceil(dist / max_seg)))
        for s in range(steps):
            t = s / float(steps)
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    if not closed:
        out.append(pts[-1])
    return out


def _ellipse_points(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    angle_deg: float = 0.0,
    num_pts: int = 40,
) -> List[Point]:
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    pts: List[Point] = []
    for i in range(num_pts):
        th = 2.0 * math.pi * i / float(num_pts)
        lx = rx * math.cos(th)
        ly = ry * math.sin(th)
        pts.append((cx + lx * ca - ly * sa, cy + lx * sa + ly * ca))
    return pts


def _rounded_rect_points(
    x0: float, y0: float, x1: float, y1: float, radius: float, steps_per_corner: int = 6
) -> List[Point]:
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    r = max(0.0, min(radius, (x1 - x0) * 0.48, (y1 - y0) * 0.48))
    if r < 1.0:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    corners = [
        (x1 - r, y0 + r, -math.pi / 2, 0.0),
        (x1 - r, y1 - r, 0.0, math.pi / 2),
        (x0 + r, y1 - r, math.pi / 2, math.pi),
        (x0 + r, y0 + r, math.pi, 1.5 * math.pi),
    ]
    pts: List[Point] = []
    for cx, cy, a0, a1 in corners:
        for i in range(steps_per_corner + 1):
            th = a0 + (a1 - a0) * (i / float(steps_per_corner))
            pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return pts


class _CrayonTextureBank:
    """Precomputed cotton paper grain, directional crayon hatch fields, and 4-phase line boil."""

    def __init__(self, width: int, height: int, seed: int) -> None:
        self.width = width
        self.height = height
        rng = np.random.default_rng(seed)

        # Fine cold-pressed paper tooth (high + medium frequency)
        raw_fine = rng.standard_normal((height, width)).astype(np.float32)
        tooth_a = gaussian_filter(raw_fine, sigma=0.85)
        tooth_b = gaussian_filter(rng.standard_normal((height, width)).astype(np.float32), sigma=2.4)
        # Subtle woven paper fiber grid
        yy = np.arange(height, dtype=np.float32)[:, None]
        xx = np.arange(width, dtype=np.float32)[None, :]
        weave = 0.12 * np.sin(xx * 0.85) + 0.12 * np.sin(yy * 0.85)
        tooth = 0.58 * (tooth_a / (np.std(tooth_a) + 1e-6)) + 0.34 * (tooth_b / (np.std(tooth_b) + 1e-6)) + weave
        # Normalize to [0, 1] via rank-like sigmoid
        self.paper_tooth = 1.0 / (1.0 + np.exp(-1.35 * tooth))

        # Crumbly wax outline grain (4 boil phases so stroke grain gently breathes every 4 frames)
        self.stroke_grain: List[np.ndarray] = []
        for p in range(4):
            g_raw = rng.standard_normal((height, width)).astype(np.float32)
            g1 = gaussian_filter(g_raw, sigma=1.05)
            g2 = rng.uniform(-0.45, 0.45, size=(height, width)).astype(np.float32)
            g = 0.68 * (g1 / (np.std(g1) + 1e-6)) + 0.55 * g2
            self.stroke_grain.append((1.0 / (1.0 + np.exp(-1.5 * g))).astype(np.float32))

        # Directional wax crayon stroke striations at -22 deg and +22 deg
        self.hatch_fields: Dict[int, np.ndarray] = {}
        for bucket in (-22, 22, 0):
            noise = rng.standard_normal((height, width)).astype(np.float32)
            # Anisotropic blur along stroke direction by shearing/rotating via PIL or 2-axis filter
            img_n = Image.fromarray(((noise * 32.0 + 128.0).clip(0, 255)).astype(np.uint8), mode="L")
            rot = img_n.rotate(-bucket, resample=Image.Resampling.BILINEAR, expand=True)
            arr_r = np.asarray(rot, dtype=np.float32)
            # Stretch strongly along X (stroke direction), tightly across Y (crayon ridge width)
            streaked = gaussian_filter(arr_r, sigma=(1.15, 16.0))
            back = Image.fromarray(streaked.clip(0, 255).astype(np.uint8), mode="L").rotate(
                bucket, resample=Image.Resampling.BILINEAR, expand=False
            )
            # Center crop back to (width, height)
            bw, bh = back.size
            left = (bw - width) // 2
            top = (bh - height) // 2
            cropped = np.asarray(back.crop((left, top, left + width, top + height)), dtype=np.float32)
            norm = (cropped - np.mean(cropped)) / (np.std(cropped) + 1e-6)
            self.hatch_fields[bucket] = (1.0 / (1.0 + np.exp(-1.4 * norm))).astype(np.float32)


_CRAYON_BANK_CACHE: Dict[Tuple[int, int, int], _CrayonTextureBank] = {}


def _get_crayon_bank(width: int, height: int, seed: int) -> _CrayonTextureBank:
    key = (width, height, seed)
    if key not in _CRAYON_BANK_CACHE:
        _CRAYON_BANK_CACHE[key] = _CrayonTextureBank(width, height, seed)
    return _CRAYON_BANK_CACHE[key]


class StyleCanvas:
    """Abstract base interface shared by CrayonCanvas and PixelCanvas."""

    style_name: str = "base"

    def __init__(self, cfg: SpecConfig, frame_idx: int, palette: Dict[str, RGB]) -> None:
        self.cfg = cfg
        self.frame_idx = frame_idx
        self.palette = palette
        self.width = cfg.width
        self.height = cfg.height

    def fill_background(self, color_key: str, shade_key: Optional[str] = None) -> None:
        raise NotImplementedError

    def light_glow_rings(
        self, cx: float, cy: float, radii: Sequence[float], color_keys: Sequence[str], densities: Sequence[float]
    ) -> None:
        raise NotImplementedError

    def polygon(
        self,
        points: Sequence[Point],
        fill_key: Optional[str] = None,
        outline_key: Optional[str] = None,
        stroke_scale: float = 1.0,
        tooth_amount: float = 0.14,
        shade_key: Optional[str] = None,
        hatch_bucket: int = -22,
        seed: int = 0,
    ) -> None:
        raise NotImplementedError

    def rounded_rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        radius: float,
        fill_key: Optional[str] = None,
        outline_key: Optional[str] = None,
        stroke_scale: float = 1.0,
        tooth_amount: float = 0.14,
        shade_key: Optional[str] = None,
        hatch_bucket: int = -22,
        seed: int = 0,
    ) -> None:
        pts = _rounded_rect_points(x0, y0, x1, y1, radius)
        self.polygon(
            pts,
            fill_key=fill_key,
            outline_key=outline_key,
            stroke_scale=stroke_scale,
            tooth_amount=tooth_amount,
            shade_key=shade_key,
            hatch_bucket=hatch_bucket,
            seed=seed,
        )

    def ellipse(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        angle_deg: float = 0.0,
        fill_key: Optional[str] = None,
        outline_key: Optional[str] = None,
        stroke_scale: float = 1.0,
        tooth_amount: float = 0.10,
        shade_key: Optional[str] = None,
        hatch_bucket: int = -22,
        seed: int = 0,
        num_pts: int = 36,
    ) -> None:
        pts = _ellipse_points(cx, cy, rx, ry, angle_deg=angle_deg, num_pts=num_pts)
        self.polygon(
            pts,
            fill_key=fill_key,
            outline_key=outline_key,
            stroke_scale=stroke_scale,
            tooth_amount=tooth_amount,
            shade_key=shade_key,
            hatch_bucket=hatch_bucket,
            seed=seed,
        )

    def polyline(
        self,
        points: Sequence[Point],
        color_key: str,
        stroke_scale: float = 1.0,
        seed: int = 0,
        closed: bool = False,
    ) -> None:
        raise NotImplementedError

    def arc_stroke(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        start_deg: float,
        end_deg: float,
        color_key: str,
        stroke_scale: float = 1.0,
        seed: int = 0,
    ) -> None:
        steps = max(8, int(abs(end_deg - start_deg) / 8.0) + 4)
        pts: List[Point] = []
        for i in range(steps + 1):
            th = math.radians(start_deg + (end_deg - start_deg) * (i / float(steps)))
            pts.append((cx + rx * math.cos(th), cy + ry * math.sin(th)))
        self.polyline(pts, color_key=color_key, stroke_scale=stroke_scale, seed=seed, closed=False)

    def steam_puff(self, cx: float, cy: float, radius: float, density: float = 0.72, seed: int = 0) -> None:
        raise NotImplementedError

    def finalize(self) -> Image.Image:
        raise NotImplementedError


class CrayonCanvas(StyleCanvas):
    """Version A: Hand-drawn wax crayon / oil pastel picture book renderer."""

    style_name = "crayon"

    def __init__(self, cfg: SpecConfig, frame_idx: int) -> None:
        super().__init__(cfg, frame_idx, cfg.palette_rgb("crayon"))
        self.bank = _get_crayon_bank(cfg.width, cfg.height, cfg.rng_seed)
        self.boil_phase = (frame_idx // max(1, cfg.line_boil_hold_frames)) % 4
        self.boil_amp = cfg.line_boil_amplitude_px
        self.brush_size = cfg.crayon_brush_size

        # Initialize canvas with warm cotton paper (#FAF1DC) + subtle tactile paper tooth (#EFE1C6)
        self.canvas = np.empty((self.height, self.width, 3), dtype=np.uint8)
        self.canvas[:, :] = self.palette["paper"]
        paper_pores = self.bank.paper_tooth < 0.14
        self.canvas[paper_pores] = self.palette["wall"]

    def _wobble_points(self, pts: Sequence[Point], seed: int, closed: bool, amp_scale: float = 1.0) -> List[Point]:
        sub = _subdivide_polyline(pts, max_seg=11.0, closed=closed)
        amp = self.boil_amp * amp_scale
        if amp <= 0.05:
            return sub
        phase_offset = (seed * 1.731 + self.boil_phase * 2.399) % (2.0 * math.pi)
        out: List[Point] = []
        for idx, (x, y) in enumerate(sub):
            # Spatial + contour-index coherent wobble so shapes breathe gently like hand-drawn frames
            a1 = 0.028 * x + 0.031 * y + phase_offset
            a2 = 0.42 * idx + phase_offset * 1.7
            dx = amp * (0.65 * math.sin(a1) + 0.35 * math.cos(a2))
            dy = amp * (0.65 * math.cos(a1 * 0.93 + 1.1) + 0.35 * math.sin(a2 * 1.13))
            out.append((x + dx, y + dy))
        return out

    def fill_background(self, color_key: str, shade_key: Optional[str] = None) -> None:
        # Leave tiny cotton-paper flecks peeking through the background crayon wash!
        hatch = self.bank.hatch_fields[-22]
        tooth = self.bank.paper_tooth
        deposit = 0.56 * tooth + 0.44 * hatch
        bg_mask = deposit > 0.19
        self.canvas[bg_mask] = self.palette[color_key]
        if shade_key is not None:
            shade_mask = deposit > 0.78
            self.canvas[shade_mask] = self.palette[shade_key]

    def light_glow_rings(
        self, cx: float, cy: float, radii: Sequence[float], color_keys: Sequence[str], densities: Sequence[float]
    ) -> None:
        """Concentric discrete dry-rubbed wax crayon halo rings (NO smooth digital gradients!)."""
        hatch = self.bank.hatch_fields[-22]
        tooth = self.bank.paper_tooth
        # Paint from largest outer ring inward
        pairs = sorted(zip(radii, color_keys, densities), key=lambda t: t[0], reverse=True)
        for r, ckey, dens in pairs:
            if r < 2:
                continue
            x0 = max(0, int(cx - r - 6))
            y0 = max(0, int(cy - r - 6))
            x1 = min(self.width, int(cx + r + 6))
            y1 = min(self.height, int(cy + r + 6))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.ogrid[y0:y1, x0:x1]
            # Slight hand-drawn wobble on ring radius by angle
            ang = np.arctan2(yy - cy, xx - cx)
            r_wobble = r + 3.0 * np.sin(5.0 * ang + self.boil_phase * 1.3) + 2.0 * np.cos(3.0 * ang)
            dist = np.hypot(xx - cx, yy - cy)
            inside = dist <= r_wobble
            # Dry-crayon radial/diagonal rub: crisp binary pigment flecks, zero smooth gradient!
            rim_factor = np.clip((r_wobble - dist) / max(8.0, r * 0.18), 0.0, 1.0)
            tex = 0.52 * hatch[y0:y1, x0:x1] + 0.48 * tooth[y0:y1, x0:x1]
            wax_hit = inside & ((tex + 0.28 * rim_factor) > (1.0 - dens))
            sub = self.canvas[y0:y1, x0:x1]
            sub[wax_hit] = self.palette[ckey]

    def _draw_crayon_stroke_bbox(
        self, pts: Sequence[Point], color_key: str, width_px: float, closed: bool
    ) -> None:
        if len(pts) < 2 or width_px < 0.8:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pad = int(math.ceil(width_px * 1.6 + 6))
        x0 = max(0, int(math.floor(min(xs))) - pad)
        y0 = max(0, int(math.floor(min(ys))) - pad)
        x1 = min(self.width, int(math.ceil(max(xs))) + pad)
        y1 = min(self.height, int(math.ceil(max(ys))) + pad)
        if x1 <= x0 or y1 <= y0:
            return

        bw, bh = x1 - x0, y1 - y0
        mask_img = Image.new("L", (bw, bh), 0)
        draw = ImageDraw.Draw(mask_img)
        shifted = [(p[0] - x0, p[1] - y0) for p in pts]
        if closed:
            shifted = shifted + [shifted[0]]
        w_int = max(2, int(round(width_px)))
        draw.line(shifted, fill=255, width=w_int, joint="curve")
        # Round endcaps
        r_cap = max(1.0, width_px * 0.46)
        for px, py in (shifted[0], shifted[-1]):
            draw.ellipse((px - r_cap, py - r_cap, px + r_cap, py + r_cap), fill=255)

        m = np.asarray(mask_img, dtype=np.float32) / 255.0
        # Blur mask slightly ONLY to compute distance-from-center for dry crumbly crayon edges,
        # then threshold crisply against paper_tooth + stroke_grain so output is 100% palette-pure!
        profile = gaussian_filter(m, sigma=max(0.7, width_px * 0.16))
        grain = self.bank.stroke_grain[self.boil_phase][y0:y1, x0:x1]
        tooth = self.bank.paper_tooth[y0:y1, x0:x1]
        # Center of crayon stroke is solid (~96%), outer 2px crumbles on paper grain!
        wax_stroke = (profile * 0.72 + (0.55 * grain + 0.45 * tooth) * 0.46) > 0.50
        wax_stroke &= profile > 0.14
        sub = self.canvas[y0:y1, x0:x1]
        sub[wax_stroke] = self.palette[color_key]

    def polygon(
        self,
        points: Sequence[Point],
        fill_key: Optional[str] = None,
        outline_key: Optional[str] = None,
        stroke_scale: float = 1.0,
        tooth_amount: float = 0.14,
        shade_key: Optional[str] = None,
        hatch_bucket: int = -22,
        seed: int = 0,
    ) -> None:
        if len(points) < 3:
            return
        wpts = self._wobble_points(points, seed=seed, closed=True, amp_scale=min(1.0, stroke_scale))
        if fill_key is not None:
            xs = [p[0] for p in wpts]
            ys = [p[1] for p in wpts]
            pad = 8
            x0 = max(0, int(math.floor(min(xs))) - pad)
            y0 = max(0, int(math.floor(min(ys))) - pad)
            x1 = min(self.width, int(math.ceil(max(xs))) + pad)
            y1 = min(self.height, int(math.ceil(max(ys))) + pad)
            if x1 > x0 and y1 > y0:
                bw, bh = x1 - x0, y1 - y0
                mask_img = Image.new("L", (bw, bh), 0)
                draw = ImageDraw.Draw(mask_img)
                shifted = [(p[0] - x0, p[1] - y0) for p in wpts]
                draw.polygon(shifted, fill=255)
                inside = np.asarray(mask_img, dtype=bool)
                if np.any(inside):
                    # Distance from edge inside polygon for authentic dry-crayon edge bristle
                    dist_in = distance_transform_edt(inside)
                    edge_ramp = np.clip(dist_in / 5.5, 0.25, 1.0)
                    hb = hatch_bucket if hatch_bucket in self.bank.hatch_fields else -22
                    hatch = self.bank.hatch_fields[hb][y0:y1, x0:x1]
                    tooth = self.bank.paper_tooth[y0:y1, x0:x1]
                    tex = 0.56 * tooth + 0.44 * hatch

                    # Where wax hits paper peaks -> solid fill color; tiny deep paper pores stay cream/underlying!
                    hit = inside & ((tex * 0.65 + edge_ramp * 0.55) > (0.30 + tooth_amount * 0.95))
                    sub = self.canvas[y0:y1, x0:x1]
                    sub[hit] = self.palette[fill_key]

                    if shade_key is not None:
                        # Visible diagonal hand-rubbed wax crayon stroke streaks in paired palette tone
                        ridge = hit & (hatch > 0.66) & (tooth > 0.44)
                        sub[ridge] = self.palette[shade_key]

        if outline_key is not None and stroke_scale > 0.0:
            self._draw_crayon_stroke_bbox(
                wpts, color_key=outline_key, width_px=self.brush_size * stroke_scale, closed=True
            )

    def polyline(
        self,
        points: Sequence[Point],
        color_key: str,
        stroke_scale: float = 1.0,
        seed: int = 0,
        closed: bool = False,
    ) -> None:
        if len(points) < 2:
            return
        wpts = self._wobble_points(points, seed=seed, closed=closed, amp_scale=min(1.0, stroke_scale * 0.85))
        self._draw_crayon_stroke_bbox(
            wpts, color_key=color_key, width_px=self.brush_size * stroke_scale, closed=closed
        )

    def steam_puff(self, cx: float, cy: float, radius: float, density: float = 0.72, seed: int = 0) -> None:
        """Fluffy dry-chalk white wax crayon steam puff."""
        if radius < 2.0 or density <= 0.05:
            return
        r = radius
        x0 = max(0, int(cx - r - 5))
        y0 = max(0, int(cy - r - 5))
        x1 = min(self.width, int(cx + r + 5))
        y1 = min(self.height, int(cy + r + 5))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        dist = np.hypot(xx - cx, yy - cy)
        falloff = np.clip(1.0 - (dist / r) ** 1.6, 0.0, 1.0)
        tooth = self.bank.paper_tooth[y0:y1, x0:x1]
        grain = self.bank.stroke_grain[(self.boil_phase + seed) % 4][y0:y1, x0:x1]
        hit = (dist <= r) & ((0.50 * falloff + 0.30 * tooth + 0.25 * grain) > (1.0 - 0.58 * density))
        self.canvas[y0:y1, x0:x1][hit] = self.palette["steam"]

    def finalize(self) -> Image.Image:
        return Image.fromarray(self.canvas, mode="RGB")


class PixelCanvas(StyleCanvas):
    """Version B: 16-bit SNES/GBA retro console pixel art renderer (320x180 -> 4x NEAREST)."""

    style_name = "pixel"

    def __init__(self, cfg: SpecConfig, frame_idx: int) -> None:
        super().__init__(cfg, frame_idx, cfg.palette_rgb("pixel"))
        self.scale_div = cfg.pixel_upscale  # 4
        self.pw = cfg.pixel_native_width    # 320
        self.ph = cfg.pixel_native_height   # 180
        self.canvas = np.empty((self.ph, self.pw, 3), dtype=np.uint8)
        self.canvas[:, :] = self.palette["wall"]

        # Tile 4x4 Bayer matrix over 320x180 native grid
        reps_y = (self.ph + 3) // 4
        reps_x = (self.pw + 3) // 4
        self.bayer = np.tile(BAYER_4X4, (reps_y, reps_x))[: self.ph, : self.pw]

    def _to_px(self, pts: Sequence[Point]) -> List[Tuple[int, int]]:
        s = float(self.scale_div)
        return [(int(round(x / s)), int(round(y / s))) for x, y in pts]

    def fill_background(self, color_key: str, shade_key: Optional[str] = None) -> None:
        self.canvas[:, :] = self.palette[color_key]
        if shade_key is not None:
            # Retro 16-bit subtle bottom/top ordered dither band
            yy = np.linspace(0.0, 1.0, self.ph, dtype=np.float32)[:, None]
            dither_band = (yy < 0.22) & (self.bayer > (yy / 0.22) * 0.85 + 0.15)
            self.canvas[dither_band] = self.palette[shade_key]

    def light_glow_rings(
        self, cx: float, cy: float, radii: Sequence[float], color_keys: Sequence[str], densities: Sequence[float]
    ) -> None:
        """Stepped 16-bit Bayer ordered-dithered light rings."""
        s = float(self.scale_div)
        pcx = int(round(cx / s))
        pcy = int(round(cy / s))
        pairs = sorted(zip(radii, color_keys, densities), key=lambda t: t[0], reverse=True)
        yy, xx = np.ogrid[0 : self.ph, 0 : self.pw]
        dist = np.hypot(xx - pcx, yy - pcy)
        for r, ckey, dens in pairs:
            pr = r / s
            if pr < 1.0:
                continue
            inside = dist <= pr
            # Crisp 2-band ordered dither: solid core + Bayer-dithered outer ring
            core = dist <= (pr * 0.68)
            dither_hit = inside & (core | (self.bayer < dens))
            self.canvas[dither_hit] = self.palette[ckey]

    def _draw_pixel_line(self, p0: Tuple[int, int], p1: Tuple[int, int], rgb: RGB, thickness: int = 1) -> None:
        """Integer Bresenham line on 320x180 grid — zero anti-aliasing!"""
        x0, y0 = p0
        x1, y1 = p1
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if thickness <= 1:
                if 0 <= x0 < self.pw and 0 <= y0 < self.ph:
                    self.canvas[y0, x0] = rgb
            else:
                for oy in range(-(thickness // 2), (thickness + 1) // 2):
                    for ox in range(-(thickness // 2), (thickness + 1) // 2):
                        nx, ny = x0 + ox, y0 + oy
                        if 0 <= nx < self.pw and 0 <= ny < self.ph:
                            self.canvas[ny, nx] = rgb
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def polygon(
        self,
        points: Sequence[Point],
        fill_key: Optional[str] = None,
        outline_key: Optional[str] = None,
        stroke_scale: float = 1.0,
        tooth_amount: float = 0.14,
        shade_key: Optional[str] = None,
        hatch_bucket: int = -22,
        seed: int = 0,
    ) -> None:
        if len(points) < 3:
            return
        ppts = self._to_px(points)
        if fill_key is not None:
            # Binary mode "1" polygon fill guarantees ZERO anti-aliased intermediate pixels
            mask_img = Image.new("1", (self.pw, self.ph), 0)
            draw = ImageDraw.Draw(mask_img)
            draw.polygon(ppts, fill=1)
            inside = np.asarray(mask_img, dtype=bool)
            self.canvas[inside] = self.palette[fill_key]
            if shade_key is not None and np.any(inside):
                ys, _ = np.nonzero(inside)
                y_min, y_max = int(ys.min()), int(ys.max())
                span = max(1, y_max - y_min)
                yy = np.arange(self.ph)[:, None]
                rel_y = (yy - y_min) / float(span)
                # Bottom edge 16-bit ordered dither shading
                dither_shade = inside & (rel_y > 0.72) & (self.bayer < 0.5)
                self.canvas[dither_shade] = self.palette[shade_key]

        if outline_key is not None and stroke_scale > 0.0:
            rgb = self.palette[outline_key]
            thick = 2 if stroke_scale >= 1.55 else 1
            n = len(ppts)
            for i in range(n):
                self._draw_pixel_line(ppts[i], ppts[(i + 1) % n], rgb, thickness=thick)

    def polyline(
        self,
        points: Sequence[Point],
        color_key: str,
        stroke_scale: float = 1.0,
        seed: int = 0,
        closed: bool = False,
    ) -> None:
        if len(points) < 2:
            return
        ppts = self._to_px(points)
        rgb = self.palette[color_key]
        thick = 2 if stroke_scale >= 1.45 else 1
        n = len(ppts)
        limit = n if closed else n - 1
        for i in range(limit):
            self._draw_pixel_line(ppts[i], ppts[(i + 1) % n], rgb, thickness=thick)

    def steam_puff(self, cx: float, cy: float, radius: float, density: float = 0.72, seed: int = 0) -> None:
        """Crisp 16-bit pixel cloud cluster with Bayer-dithered outer pixels."""
        s = float(self.scale_div)
        pcx = int(round(cx / s))
        pcy = int(round(cy / s))
        pr = max(1.2, radius / s)
        x0 = max(0, int(pcx - pr - 2))
        y0 = max(0, int(pcy - pr - 2))
        x1 = min(self.pw, int(pcx + pr + 2))
        y1 = min(self.ph, int(pcy + pr + 2))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        dist = np.hypot(xx - pcx, yy - pcy)
        core = (dist <= pr * 0.62) & (density > 0.35)
        rim = (dist <= pr) & (self.bayer[y0:y1, x0:x1] < density * 0.85)
        hit = core | rim
        self.canvas[y0:y1, x0:x1][hit] = self.palette["steam"]

    def finalize(self) -> Image.Image:
        small = Image.fromarray(self.canvas, mode="RGB")
        return small.resize((self.width, self.height), resample=Image.Resampling.NEAREST)


def make_canvas(style: str, cfg: SpecConfig, frame_idx: int) -> StyleCanvas:
    if style == "crayon":
        return CrayonCanvas(cfg, frame_idx)
    if style == "pixel":
        return PixelCanvas(cfg, frame_idx)
    raise ValueError(f"Unsupported style '{style}'. Expected 'crayon' or 'pixel'.")
