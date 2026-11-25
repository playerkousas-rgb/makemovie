"""Unified camera rig and easing curves shared 100% across Version A and Version B."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from spec_loader import SpecConfig


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def smoothstep(t: float) -> float:
    x = clamp(t, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smootherstep(t: float) -> float:
    x = clamp(t, 0.0, 1.0)
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass(frozen=True)
class CameraState:
    shot_id: int          # 1, 2, or 3
    frame_idx: int        # 0..191
    shot_frame: int       # local frame within shot
    shot_progress: float  # 0.0..1.0 within shot
    time_sec: float       # 0.0..8.0
    zoom: float           # camera magnification
    focus_x: float        # normalized world focus [0, 1]
    focus_y: float        # normalized world focus [0, 1]
    width: int            # virtual canvas width (1280)
    height: int           # virtual canvas height (720)

    def project(self, wx: float, wy: float) -> Tuple[float, float]:
        """Map virtual world coordinates (in 1280x720 stage space) to screen pixels."""
        cx = self.focus_x * self.width
        cy = self.focus_y * self.height
        sx = (wx - cx) * self.zoom + self.width * 0.5
        sy = (wy - cy) * self.zoom + self.height * 0.5
        return sx, sy

    def project_norm(self, nx: float, ny: float) -> Tuple[float, float]:
        """Map normalized stage coordinates (0..1, 0..1) to 1280x720 screen pixels."""
        return self.project(nx * self.width, ny * self.height)

    def scale(self, length: float) -> float:
        return length * self.zoom


def get_camera_state(frame_idx: int, cfg: SpecConfig) -> CameraState:
    t_sec = frame_idx / float(cfg.fps)

    s1_start, s1_end = cfg.shot1_frames
    s2_start, s2_end = cfg.shot2_frames
    s3_start, s3_end = cfg.shot3_frames

    if frame_idx <= s1_end:
        shot_id = 1
        local_f = frame_idx - s1_start
        denom = max(1, s1_end - s1_start)
        u = local_f / float(denom)
        e = smoothstep(u)
        zoom = lerp(1.00, 1.16, e)
        fx = lerp(0.51, 0.59, e)
        fy = lerp(0.51, 0.54, e)
    elif frame_idx <= s2_end:
        shot_id = 2
        local_f = frame_idx - s2_start
        denom = max(1, s2_end - s2_start)
        u = local_f / float(denom)
        e = smoothstep(u)
        zoom = lerp(1.00, 1.03, e)
        fx = lerp(0.49, 0.52, e)
        fy = lerp(0.52, 0.53, e)
    else:
        shot_id = 3
        local_f = frame_idx - s3_start
        denom = max(1, s3_end - s3_start)
        u = local_f / float(denom)
        e = smoothstep(u)
        zoom = lerp(1.00, 1.06, e)
        fx = lerp(0.50, 0.505, e)
        fy = lerp(0.505, 0.50, e)

    return CameraState(
        shot_id=shot_id,
        frame_idx=frame_idx,
        shot_frame=local_f,
        shot_progress=u,
        time_sec=t_sec,
        zoom=zoom,
        focus_x=fx,
        focus_y=fy,
        width=cfg.width,
        height=cfg.height,
    )
