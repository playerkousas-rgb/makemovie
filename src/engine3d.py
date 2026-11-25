"""Vectorized Analytic 3D Ray-Primitive Studio Renderer (NumPy).
Renders true 3D perspective scenes with smooth vinyl-toy ('波波圓滑 3D') & beveled blocky ('方塊 3D')
geometry, exact Z-buffering, 3-point Half-Lambert + Blinn-Phong studio lighting, rim light,
analytic ground contact shadows, and 3D surface-locked Scout badges.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Vec3 = Tuple[float, float, float]
RGBf = Tuple[float, float, float]


def v3(x: float, y: float, z: float) -> np.ndarray:
    return np.array([x, y, z], dtype=np.float32)


def normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / max(1e-7, n)


def rot_x(deg: float) -> np.ndarray:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)


def rot_y(deg: float) -> np.ndarray:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)


def rot_z(deg: float) -> np.ndarray:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float32)


def hex_rgb01(hex_str: str) -> RGBf:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


@dataclass
class Camera3D:
    pos: np.ndarray       # (3,) camera position in world space (Y up)
    target: np.ndarray    # (3,) look-at target
    fov_deg: float = 34.0
    roll_deg: float = 0.0


class Scene3D:
    """Analytic 3D Ray-Buffer renderer optimized with tight screen-space bounding-box culling."""

    def __init__(
        self,
        width: int,
        height: int,
        cam: Camera3D,
        bg_top: RGBf = (0.76, 0.89, 0.97),
        bg_bot: RGBf = (0.91, 0.96, 0.99),
        floor_y: Optional[float] = 0.0,
        floor_color: RGBf = (0.85, 0.92, 0.97),
        key_dir: Vec3 = (-0.52, 0.72, 0.62),
        rim_color: RGBf = (0.88, 0.95, 1.00),
    ) -> None:
        self.w = width
        self.h = height
        self.cam = cam
        self.bg_top = bg_top
        self.bg_bot = bg_bot
        self.floor_y = floor_y
        self.floor_color = floor_color
        self.key_dir = normalize(np.array(key_dir, dtype=np.float32))
        self.rim_color = np.array(rim_color, dtype=np.float32)

        # Build camera basis (right, up, forward)
        fwd = normalize(cam.target - cam.pos)
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        right = normalize(np.cross(fwd, world_up))
        up = normalize(np.cross(right, fwd))
        if abs(cam.roll_deg) > 1e-3:
            rr = math.radians(cam.roll_deg)
            cr, sr = math.cos(rr), math.sin(rr)
            right, up = cr * right + sr * up, -sr * right + cr * up

        self.cam_pos = cam.pos.astype(np.float32)
        self.cam_right = right
        self.cam_up = up
        self.cam_fwd = fwd
        self.tan_half_fov = math.tan(math.radians(cam.fov_deg * 0.5))
        self.aspect = width / float(height)

        # Precompute primary ray directions (H, W, 3)
        ndc_x = ((np.arange(width, dtype=np.float32) + 0.5) / width * 2.0 - 1.0) * self.aspect * self.tan_half_fov
        ndc_y = (1.0 - (np.arange(height, dtype=np.float32) + 0.5) / height * 2.0) * self.tan_half_fov
        rx = fwd[0] + ndc_x[None, :] * right[0] + ndc_y[:, None] * up[0]
        ry = fwd[1] + ndc_x[None, :] * right[1] + ndc_y[:, None] * up[1]
        rz = fwd[2] + ndc_x[None, :] * right[2] + ndc_y[:, None] * up[2]
        inv_len = 1.0 / np.sqrt(rx * rx + ry * ry + rz * rz)
        self.rd = np.stack([rx * inv_len, ry * inv_len, rz * inv_len], axis=-1).astype(np.float32)

        # G-buffers
        self.t_buf = np.full((height, width), 1e9, dtype=np.float32)
        self.n_buf = np.zeros((height, width, 3), dtype=np.float32)
        self.c_buf = np.zeros((height, width, 3), dtype=np.float32)
        self.r_buf = np.full((height, width), 0.5, dtype=np.float32)
        self.emissive_buf = np.zeros((height, width, 3), dtype=np.float32)

        # Shadow casters on floor (wx, wz, radius, strength)
        self.shadow_blobs: List[Tuple[float, float, float, float]] = []

    def project_bbox(self, center: np.ndarray, bound_r: float) -> Optional[Tuple[int, int, int, int]]:
        """Project a 3D bounding sphere (center, bound_r) to tight 2D pixel bounds [x0, y0, x1, y1]."""
        rel = center - self.cam_pos
        cz = float(np.dot(rel, self.cam_fwd))
        if cz + bound_r <= 0.15:
            return None
        if cz - bound_r <= 0.15:
            return (0, 0, self.w, self.h)

        cx = float(np.dot(rel, self.cam_right))
        cy = float(np.dot(rel, self.cam_up))
        # Conservative angular half-extent for perspective projection off-axis
        d2 = cx * cx + cy * cy + cz * cz
        sin_a = min(0.98, bound_r / max(bound_r + 1e-4, math.sqrt(d2)))
        tan_a = sin_a / math.sqrt(max(1e-4, 1.0 - sin_a * sin_a))
        z_eff = max(0.2, cz - bound_r)
        pad_ndc_y = (bound_r / z_eff + tan_a * 0.35) / self.tan_half_fov * 1.12
        pad_ndc_x = pad_ndc_y / self.aspect

        proj_x = (cx / cz) / (self.aspect * self.tan_half_fov)
        proj_y = (cy / cz) / self.tan_half_fov

        u0 = (proj_x - pad_ndc_x) * 0.5 + 0.5
        u1 = (proj_x + pad_ndc_x) * 0.5 + 0.5
        v0 = 0.5 - (proj_y + pad_ndc_y) * 0.5
        v1 = 0.5 - (proj_y - pad_ndc_y) * 0.5

        x0 = max(0, int(math.floor(u0 * self.w)) - 3)
        x1 = min(self.w, int(math.ceil(u1 * self.w)) + 3)
        y0 = max(0, int(math.floor(v0 * self.h)) - 3)
        y1 = min(self.h, int(math.ceil(v1 * self.h)) + 3)
        if x1 <= x0 or y1 <= y0:
            return None
        return (x0, y0, x1, y1)

    def project_point(self, pt: np.ndarray) -> Tuple[float, float, float]:
        """Project a 3D world point to (screen_x, screen_y, depth_z)."""
        rel = pt - self.cam_pos
        cz = max(0.05, float(np.dot(rel, self.cam_fwd)))
        cx = float(np.dot(rel, self.cam_right))
        cy = float(np.dot(rel, self.cam_up))
        u = (cx / cz) / (self.aspect * self.tan_half_fov) * 0.5 + 0.5
        v = 0.5 - (cy / cz) / self.tan_half_fov * 0.5
        return (u * self.w, v * self.h, cz)

    def add_floor_shadow(self, wx: float, wz: float, radius: float, strength: float = 0.28) -> None:
        self.shadow_blobs.append((wx, wz, radius, strength))

    def _commit_hit(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        valid: np.ndarray,
        t_hit: np.ndarray,
        n_world: np.ndarray,
        color: RGBf | np.ndarray,
        roughness: float,
        emissive: Optional[RGBf] = None,
    ) -> None:
        t_sub = self.t_buf[y0:y1, x0:x1]
        win = valid & (t_hit > 0.1) & (t_hit < t_sub)
        if not np.any(win):
            return
        t_sub[win] = t_hit[win]
        self.n_buf[y0:y1, x0:x1][win] = n_world[win]
        if isinstance(color, np.ndarray) and color.ndim == 3:
            self.c_buf[y0:y1, x0:x1][win] = color[win]
        else:
            self.c_buf[y0:y1, x0:x1][win] = np.array(color, dtype=np.float32)
        self.r_buf[y0:y1, x0:x1][win] = roughness
        if emissive is not None:
            self.emissive_buf[y0:y1, x0:x1][win] = np.array(emissive, dtype=np.float32)
        else:
            self.emissive_buf[y0:y1, x0:x1][win] = 0.0

    def add_sphere(
        self,
        center: np.ndarray,
        radius: float,
        color: RGBf,
        roughness: float = 0.48,
        emissive: Optional[RGBf] = None,
    ) -> None:
        bb = self.project_bbox(center, radius)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd = self.rd[y0:y1, x0:x1]
        oc = self.cam_pos - center
        b = np.einsum("ijk,k->ij", rd, oc)
        c = float(np.dot(oc, oc) - radius * radius)
        disc = b * b - c
        valid = disc > 0.0
        if not np.any(valid):
            return
        sq = np.sqrt(np.maximum(0.0, disc))
        t = -b - sq
        p = self.cam_pos + t[..., None] * rd
        n = (p - center) / radius
        self._commit_hit(x0, y0, x1, y1, valid, t, n, color, roughness, emissive)

    def add_ellipsoid(
        self,
        center: np.ndarray,
        radii: Vec3,
        color: RGBf,
        rot: Optional[np.ndarray] = None,
        roughness: float = 0.48,
        emissive: Optional[RGBf] = None,
    ) -> None:
        rx, ry, rz = radii
        max_r = max(rx, ry, rz)
        bb = self.project_bbox(center, max_r)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd_w = self.rd[y0:y1, x0:x1]
        oc_w = self.cam_pos - center
        if rot is not None:
            oc_l = rot.T @ oc_w
            rd_l = np.einsum("ij,hwj->hwi", rot.T, rd_w)
        else:
            oc_l = oc_w
            rd_l = rd_w

        inv_r = np.array([1.0 / rx, 1.0 / ry, 1.0 / rz], dtype=np.float32)
        ro_n = oc_l * inv_r
        rd_n = rd_l * inv_r
        a = np.sum(rd_n * rd_n, axis=-1)
        b = np.einsum("hwi,i->hw", rd_n, ro_n)
        c = float(np.dot(ro_n, ro_n) - 1.0)
        disc = b * b - a * c
        valid = disc > 0.0
        if not np.any(valid):
            return
        t = (-b - np.sqrt(np.maximum(0.0, disc))) / np.maximum(1e-7, a)
        p_l = oc_l + t[..., None] * rd_l
        n_l = p_l * (inv_r * inv_r)
        n_len = np.linalg.norm(n_l, axis=-1, keepdims=True)
        n_l = n_l / np.maximum(1e-7, n_len)
        n_w = np.einsum("ij,hwj->hwi", rot, n_l) if rot is not None else n_l
        self._commit_hit(x0, y0, x1, y1, valid, t, n_w, color, roughness, emissive)

    def add_capsule(
        self,
        pa: np.ndarray,
        pb: np.ndarray,
        radius: float,
        color: RGBf,
        roughness: float = 0.50,
        emissive: Optional[RGBf] = None,
    ) -> None:
        """Exact closed-form ray-capsule intersection (Inigo Quilez formula)."""
        mid = 0.5 * (pa + pb)
        half_len = 0.5 * float(np.linalg.norm(pb - pa))
        bb = self.project_bbox(mid, half_len + radius)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd = self.rd[y0:y1, x0:x1]

        ba = pb - pa
        oa = self.cam_pos - pa
        baba = float(np.dot(ba, ba))
        if baba < 1e-6:
            self.add_sphere(pa, radius, color, roughness, emissive)
            return

        bard = np.einsum("k,hwk->hw", ba, rd)
        baoa = float(np.dot(ba, oa))
        rdoa = np.einsum("hwk,k->hw", rd, oa)
        oaoa = float(np.dot(oa, oa))

        a = baba - bard * bard
        b = baba * rdoa - baoa * bard
        c = baba * oaoa - baoa * baoa - radius * radius * baba

        h = b * b - a * c
        valid = np.zeros(rd.shape[:2], dtype=bool)
        t_out = np.full(rd.shape[:2], 1e9, dtype=np.float32)

        cond_cyl = h >= 0.0
        if np.any(cond_cyl):
            t_cyl = (-b - np.sqrt(np.maximum(0.0, h))) / np.maximum(1e-7, a)
            y = baoa + t_cyl * bard
            body_hit = cond_cyl & (y > 0.0) & (y < baba)
            valid |= body_hit
            t_out = np.where(body_hit, t_cyl, t_out)

            # Cap hits
            oc_cap = np.where((y <= 0.0)[..., None], oa, self.cam_pos - pb)
            b_cap = np.einsum("hwk,hwk->hw", rd, oc_cap)
            c_cap = np.sum(oc_cap * oc_cap, axis=-1) - radius * radius
            h_cap = b_cap * b_cap - c_cap
            cap_hit = cond_cyl & (~body_hit) & (h_cap > 0.0)
            t_cap = -b_cap - np.sqrt(np.maximum(0.0, h_cap))
            valid |= cap_hit
            t_out = np.where(cap_hit, t_cap, t_out)

        if not np.any(valid):
            return

        p = self.cam_pos + t_out[..., None] * rd
        pa_p = p - pa
        h_proj = np.clip(np.einsum("hwk,k->hw", pa_p, ba) / baba, 0.0, 1.0)
        n = (pa_p - h_proj[..., None] * ba) / radius
        self._commit_hit(x0, y0, x1, y1, valid, t_out, n, color, roughness, emissive)

    def add_cylinder(
        self,
        pa: np.ndarray,
        pb: np.ndarray,
        radius: float,
        color: RGBf,
        roughness: float = 0.42,
        emissive: Optional[RGBf] = None,
    ) -> None:
        """Exact closed-form ray-capped-cylinder intersection (for turntables, badges, berets)."""
        mid = 0.5 * (pa + pb)
        half_len = 0.5 * float(np.linalg.norm(pb - pa))
        bb = self.project_bbox(mid, math.hypot(half_len, radius))
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd = self.rd[y0:y1, x0:x1]

        ca = pb - pa
        oc = self.cam_pos - pa
        caca = float(np.dot(ca, ca))
        if caca < 1e-7:
            return
        card = np.einsum("k,hwk->hw", ca, rd)
        caoc = float(np.dot(ca, oc))

        a = caca - card * card
        b = caca * np.einsum("hwk,k->hw", rd, oc) - caoc * card
        c = caca * float(np.dot(oc, oc)) - caoc * caoc - radius * radius * caca
        h = b * b - a * c

        valid = h >= 0.0
        if not np.any(valid):
            return
        sq = np.sqrt(np.maximum(0.0, h))
        t_body = (-b - sq) / np.maximum(1e-7, a)
        y_body = caoc + t_body * card

        hit_body = valid & (y_body > 0.0) & (y_body < caca)

        # Cap intersections
        t_cap = (np.where(y_body < 0.0, 0.0, caca) - caoc) / np.where(np.abs(card) < 1e-7, 1e-7, card)
        hit_cap = valid & (~hit_body) & (np.abs(b + a * t_cap) < sq)

        final_valid = hit_body | hit_cap
        if not np.any(final_valid):
            return

        t_hit = np.where(hit_body, t_body, t_cap)
        n_axis = ca / math.sqrt(caca)
        p_rel = oc + t_hit[..., None] * rd
        n_body = (p_rel - (y_body / caca)[..., None] * ca) / radius
        cap_sign = np.where(y_body < 0.0, -1.0, 1.0)[..., None]
        n_cap = cap_sign * n_axis
        n_out = np.where(hit_body[..., None], n_body, n_cap)
        self._commit_hit(x0, y0, x1, y1, final_valid, t_hit, n_out, color, roughness, emissive)

    def add_rounded_box(
        self,
        center: np.ndarray,
        half_extents: Vec3,
        bevel_r: float,
        color: RGBf,
        rot: Optional[np.ndarray] = None,
        roughness: float = 0.48,
        emissive: Optional[RGBf] = None,
    ) -> None:
        """Exact ray-box slab pre-cull + local rounded-box SDF sphere-tracing (12 steps).
        Produces silky-smooth beveled 3D boxes for torsos, shorts, books, UI cards & Blocky Scouts!
        """
        hx, hy, hz = half_extents
        bound_r = math.sqrt(hx * hx + hy * hy + hz * hz) + 0.02
        bb = self.project_bbox(center, bound_r)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd_w = self.rd[y0:y1, x0:x1]
        oc_w = self.cam_pos - center
        if rot is not None:
            ro = rot.T @ oc_w
            rd = np.einsum("ij,hwj->hwi", rot.T, rd_w)
        else:
            ro = oc_w
            rd = rd_w

        # Fast outer AABB slab intersection to skip 80%+ non-hitting rays immediately!
        outer = np.array([hx, hy, hz], dtype=np.float32)
        inv_d = 1.0 / np.where(np.abs(rd) < 1e-6, 1e-6, rd)
        t1 = (-outer - ro) * inv_d
        t2 = (outer - ro) * inv_d
        tmin = np.max(np.minimum(t1, t2), axis=-1)
        tmax = np.min(np.maximum(t1, t2), axis=-1)
        ray_mask = (tmax >= np.maximum(0.05, tmin))
        if not np.any(ray_mask):
            return

        r_bev = min(bevel_r, min(hx, hy, hz) * 0.92)
        inner = np.maximum(1e-4, outer - r_bev)

        # Only march active pixels in 1D flattened array for blazing speed!
        ys, xs = np.nonzero(ray_mask)
        rd_a = rd[ys, xs]  # (M, 3)
        t_cur = np.maximum(0.05, tmin[ys, xs]).astype(np.float32)
        t_end = tmax[ys, xs].astype(np.float32) + r_bev * 0.5

        for _ in range(11):
            p = ro + t_cur[:, None] * rd_a
            q = np.abs(p) - inner
            q_pos = np.maximum(q, 0.0)
            outside_d = np.sqrt(np.sum(q_pos * q_pos, axis=-1))
            inside_d = np.minimum(np.max(q, axis=-1), 0.0)
            dist = outside_d + inside_d - r_bev
            t_cur = t_cur + dist

        p_hit = ro + t_cur[:, None] * rd_a
        q_f = np.abs(p_hit) - inner
        q_fpos = np.maximum(q_f, 0.0)
        final_d = np.sqrt(np.sum(q_fpos * q_fpos, axis=-1)) + np.minimum(np.max(q_f, axis=-1), 0.0) - r_bev
        hit_m = (final_d < 0.008) & (t_cur <= t_end)
        if not np.any(hit_m):
            return

        # Analytic rounded-box gradient normal!
        eps_n = np.where(q_f > 0.0, q_f, 0.0)
        # Fallback to dominant face axis if flat interior face
        max_axis = np.argmax(q_f, axis=-1)
        face_n = np.zeros_like(p_hit)
        face_n[np.arange(len(p_hit)), max_axis] = 1.0
        raw_n = np.where((np.sum(eps_n * eps_n, axis=-1, keepdims=True) > 1e-8), eps_n, face_n) * np.sign(p_hit)
        n_l = raw_n / np.maximum(1e-7, np.linalg.norm(raw_n, axis=-1, keepdims=True))
        n_w_a = (n_l @ rot.T) if rot is not None else n_l

        valid_grid = np.zeros(rd.shape[:2], dtype=bool)
        t_grid = np.full(rd.shape[:2], 1e9, dtype=np.float32)
        n_grid = np.zeros_like(rd)

        hy_idx = ys[hit_m]
        hx_idx = xs[hit_m]
        valid_grid[hy_idx, hx_idx] = True
        t_grid[hy_idx, hx_idx] = t_cur[hit_m]
        n_grid[hy_idx, hx_idx] = n_w_a[hit_m]
        self._commit_hit(x0, y0, x1, y1, valid_grid, t_grid, n_grid, color, roughness, emissive)

    def add_scout_badge_3d(
        self,
        center: np.ndarray,
        normal: np.ndarray,
        radius: float,
        base_color: RGBf,
        emblem_color: RGBf,
        shape: str = "circle",  # "circle" | "diamond" | "tape"
        glow: float = 0.0,
    ) -> None:
        """Render a true 3D Scout badge patch (with 3D thickness + embroidered border & emblem)
        oriented flush along `normal` in 3D character/world space!
        """
        n = normalize(normal)
        bb = self.project_bbox(center, radius * 1.45)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd = self.rd[y0:y1, x0:x1]

        # Build local tangent frame (u_ax, v_ax, n)
        ref_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        if abs(float(np.dot(n, ref_up))) > 0.92:
            ref_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        u_ax = normalize(np.cross(ref_up, n))
        v_ax = normalize(np.cross(n, u_ax))

        # Front plane of embroidered patch (thickness = 0.018)
        top_c = center + n * 0.018
        denom = np.einsum("hwk,k->hw", rd, n)
        valid_front = denom < -1e-4
        if not np.any(valid_front):
            return
        t = float(np.dot(top_c - self.cam_pos, n)) / np.where(valid_front, denom, -1.0)
        p = self.cam_pos + t[..., None] * rd
        rel = p - top_c
        lu = np.einsum("hwk,k->hw", rel, u_ax) / radius
        lv = np.einsum("hwk,k->hw", rel, v_ax) / radius

        if shape == "diamond":
            metric = np.abs(lu) * 0.95 + np.abs(lv) * 0.85
            inside = valid_front & (metric <= 1.0)
            border = (metric > 0.74)
            emblem = (metric < 0.42)
        elif shape == "tape":
            # Curved Hong Kong Scout shoulder troop tape (wider horizontally, arched!)
            lv_arc = lv + 0.18 * (lu * lu)
            inside = valid_front & (np.abs(lu) <= 1.32) & (np.abs(lv_arc) <= 0.46)
            border = (np.abs(lu) > 1.15) | (np.abs(lv_arc) > 0.33)
            emblem = (np.abs(lv_arc) < 0.14) & (np.abs(lu) < 0.85)
        else:
            r2 = lu * lu + lv * lv
            inside = valid_front & (r2 <= 1.0)
            border = r2 > 0.72
            # Cute stylized Scout fleur-de-lis / star emblem inside badge!
            emblem = ((np.abs(lu) < 0.16) & (np.abs(lv) < 0.50)) | ((lu * lu * 1.4 + (lv + 0.08) ** 2) < 0.16)

        if not np.any(inside):
            return

        col_arr = np.empty(rd.shape, dtype=np.float32)
        col_arr[:] = base_color
        col_arr[border | emblem] = emblem_color

        n_arr = np.broadcast_to(n, rd.shape).copy()
        # Subtle beveled rim normal on border for real 3D embroidered sheen
        rim_vec = lu[..., None] * u_ax + lv[..., None] * v_ax
        n_arr[border] = n * 0.78 + rim_vec[border] * 0.22
        n_arr /= np.maximum(1e-6, np.linalg.norm(n_arr, axis=-1, keepdims=True))

        emis = (emblem_color[0] * glow, emblem_color[1] * glow, emblem_color[2] * glow) if glow > 0.01 else None
        self._commit_hit(x0, y0, x1, y1, inside, t, n_arr, col_arr, roughness=0.35, emissive=emis)

    def add_textured_patch_3d(
        self,
        center: np.ndarray,
        normal: np.ndarray,
        u_right: np.ndarray,
        v_up: np.ndarray,
        width: float,
        height: float,
        rgba_tex: np.ndarray,
        shape: str = "rect",
        lift: float = 0.008,
        glow: float = 0.0,
    ) -> None:
        """Project an official RGBA PNG badge texture (`(H, W, 4)` float32 in [0,1]) onto an
        exact oriented 3D plane (`u_right` = artwork right, `v_up` = artwork top) in Z-buffer space.
        """
        n = normalize(normal)
        u_ax = normalize(u_right)
        v_ax = normalize(v_up)
        half_w = 0.5 * width
        half_h = 0.5 * height
        bound_r = math.hypot(half_w, half_h) + abs(lift) + 0.02
        bb = self.project_bbox(center, bound_r)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        rd = self.rd[y0:y1, x0:x1]

        top_c = center + n * lift
        denom = np.einsum("hwk,k->hw", rd, n)
        valid_front = denom < -1e-4
        if not np.any(valid_front):
            return

        t = float(np.dot(top_c - self.cam_pos, n)) / np.where(valid_front, denom, -1.0)
        p = self.cam_pos + t[..., None] * rd
        rel = p - top_c
        lu = np.einsum("hwk,k->hw", rel, u_ax) / max(1e-6, half_w)  # [-1, +1] left -> right
        lv = np.einsum("hwk,k->hw", rel, v_ax) / max(1e-6, half_h)  # [-1, +1] bottom -> top

        if shape == "circle":
            geom_in = valid_front & ((lu * lu + lv * lv) <= 1.0)
        else:
            geom_in = valid_front & (np.abs(lu) <= 1.0) & (np.abs(lv) <= 1.0)
        if not np.any(geom_in):
            return

        th, tw = rgba_tex.shape[:2]
        # Map lu in [-1,+1] -> [0, tw-1], lv in [+1,-1] -> [0, th-1] (top of image = +v_up!)
        fx = np.clip((lu * 0.5 + 0.5) * (tw - 1), 0.0, tw - 1.001)
        fy = np.clip((0.5 - lv * 0.5) * (th - 1), 0.0, th - 1.001)
        ix0 = fx.astype(np.int32)
        iy0 = fy.astype(np.int32)
        ix1 = np.minimum(tw - 1, ix0 + 1)
        iy1 = np.minimum(th - 1, iy0 + 1)
        wx = (fx - ix0)[..., None]
        wy = (fy - iy0)[..., None]

        c00 = rgba_tex[iy0, ix0]
        c10 = rgba_tex[iy0, ix1]
        c01 = rgba_tex[iy1, ix0]
        c11 = rgba_tex[iy1, ix1]
        sampled = (c00 * (1.0 - wx) + c10 * wx) * (1.0 - wy) + (c01 * (1.0 - wx) + c11 * wx) * wy

        inside = geom_in & (sampled[..., 3] > 0.25)
        if not np.any(inside):
            return

        col_arr = sampled[..., :3].astype(np.float32)
        n_arr = np.broadcast_to(n, rd.shape).copy()
        emis = (0.35 * glow, 0.30 * glow, 0.12 * glow) if glow > 0.01 else None
        self._commit_hit(x0, y0, x1, y1, inside, t, n_arr, col_arr, roughness=0.58, emissive=emis)

    def render(self) -> Image.Image:
        """Shade G-buffer with 3-point vinyl-toy studio lighting, floor shadows & edge AA."""
        # 1. Studio backdrop gradient (clean subtle vertical studio cyclorama)
        v_grad = np.linspace(0.0, 1.0, self.h, dtype=np.float32)[:, None, None]
        top = np.array(self.bg_top, dtype=np.float32)
        bot = np.array(self.bg_bot, dtype=np.float32)
        img = top * (1.0 - v_grad) + bot * v_grad
        img = np.broadcast_to(img, (self.h, self.w, 3)).copy()

        # 2. Analytic studio floor plane (y = floor_y) with soft contact shadows
        if self.floor_y is not None:
            dy = self.rd[:, :, 1]
            hit_f = dy < -1e-4
            t_f = (self.floor_y - self.cam_pos[1]) / np.where(hit_f, dy, -1.0)
            vis_f = hit_f & (t_f > 0.1) & (t_f < self.t_buf) & (t_f < 28.0)
            if np.any(vis_f):
                pf = self.cam_pos + t_f[..., None] * self.rd
                fx = pf[:, :, 0]
                fz = pf[:, :, 2]
                # Distance fade into studio cyclorama horizon so there's no harsh horizon line!
                dist_fade = np.clip(1.0 - np.hypot(fx, fz) / 14.0, 0.0, 1.0) ** 1.4
                shadow = np.zeros((self.h, self.w), dtype=np.float32)
                for sx, sz, sr, s_str in self.shadow_blobs:
                    d2 = ((fx - sx) ** 2 + (fz - sz) ** 2) / max(1e-4, sr * sr)
                    shadow = np.maximum(shadow, s_str * np.exp(-d2 * 1.8))
                fl_col = np.array(self.floor_color, dtype=np.float32) * (1.0 - shadow[..., None])
                blend = (dist_fade * 0.85)[..., None]
                img[vis_f] = img[vis_f] * (1.0 - blend[vis_f]) + fl_col[vis_f] * blend[vis_f]

        # 3. Shade foreground 3D objects (Half-Lambert wrap + Blinn-Phong + Fresnel Rim)
        fg = self.t_buf < 1e8
        if np.any(fg):
            n = self.n_buf[fg]
            c = self.c_buf[fg]
            rough = self.r_buf[fg]
            v = -self.rd[fg]

            # Key light (Half-Lambert soft wrap gives adorable SCOUT3D smooth vinyl figurine feel!)
            ndotl = np.sum(n * self.key_dir, axis=-1)
            wrap = np.clip(ndotl * 0.52 + 0.48, 0.0, 1.0) ** 1.35

            # Hemisphere sky-to-ground bounce fill
            hemi = 0.5 + 0.5 * n[:, 1]
            ambient = 0.30 + 0.16 * hemi

            # Specular highlight
            h_vec = normalize(self.key_dir + np.array([0.0, 0.0, 1.0], dtype=np.float32))
            h_pix = v + self.key_dir
            h_pix /= np.maximum(1e-6, np.linalg.norm(h_pix, axis=-1, keepdims=True))
            ndoth = np.clip(np.sum(n * h_pix, axis=-1), 0.0, 1.0)
            shininess = np.clip((1.0 - rough) * 56.0 + 8.0, 6.0, 64.0)
            spec_strength = (1.0 - rough) * 0.36
            spec = (ndoth ** shininess) * spec_strength * np.clip(ndotl + 0.2, 0.0, 1.0)

            # Soft rim backlight on silhouettes
            ndotv = np.clip(np.sum(n * v, axis=-1), 0.0, 1.0)
            rim = ((1.0 - ndotv) ** 3.0) * (0.24 + 0.18 * np.clip(n[:, 1], 0.0, 1.0))

            shaded = (
                c * (ambient + 0.68 * wrap)[:, None]
                + spec[:, None] * np.array([1.0, 0.98, 0.94], dtype=np.float32)
                + rim[:, None] * self.rim_color * 0.55
                + self.emissive_buf[fg]
            )
            img[fg] = np.clip(shaded, 0.0, 1.0)

        # 4. Crisp silhouette edge anti-aliasing pass (selective depth-edge smoothing)
        depth_clamped = np.minimum(self.t_buf, 30.0)
        gx = np.abs(np.diff(depth_clamped, axis=1, prepend=depth_clamped[:, :1]))
        gy = np.abs(np.diff(depth_clamped, axis=0, prepend=depth_clamped[:1, :]))
        edge_mask = ((gx + gy) > 0.08)[..., None]
        if np.any(edge_mask):
            blurred = gaussian_filter(img, sigma=(0.72, 0.72, 0.0))
            img = np.where(edge_mask, 0.55 * img + 0.45 * blurred, img)

        # Subtle sRGB-friendly contrast curve
        out_u8 = np.clip(img * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(out_u8, mode="RGB")
