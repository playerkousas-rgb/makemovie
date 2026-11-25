"""Load animation parameters and rules from specs/001..099 markdown files."""

from __future__ import annotations

import glob
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
FONT_CACHE_DIR = REPO_ROOT / ".cache" / "fonts"

FONT_BLOBS = {
    "Iansui-Regular.ttf": "https://api.github.com/repos/ButTaiwan/iansui/git/blobs/3dcc17971252ea3c23f1eac4e6277e762f4566d0",
    "LXGWWenKaiTC-Medium.ttf": "https://api.github.com/repos/lxgw/LxgwWenkaiTC/git/blobs/95b6fd9cfcb1d0b10e7327fe1f807830ea29a7c3",
    "Cubic_11.ttf": "https://api.github.com/repos/ACh-K/Cubic-11/git/blobs/48b3411ce6f6f54db45b6125d108b574ebdc973e",
}


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    if rgb == (0, 0, 0):
        raise ValueError("Pure black #000000 is strictly forbidden by specs/01-color!")
    return rgb


DEFAULT_CRAYON_HEX: Dict[str, str] = {
    "paper": "#FAF1DC",
    "outline": "#3D2516",
    "night": "#2B3A55",
    "night_mid": "#3E5172",
    "moon": "#F6E7B8",
    "wall": "#EFE1C6",
    "wall_shade": "#E2CEAC",
    "shelf": "#6E9887",
    "shelf_dark": "#4E7465",
    "accent_coral": "#E07A5F",
    "accent_berry": "#B56576",
    "counter": "#C88A55",
    "counter_dark": "#9E6336",
    "steamer": "#D9CFC1",
    "steamer_dark": "#A89B8C",
    "glass_tint": "#EBF2F0",
    "glow": "#F4B942",
    "glow_inner": "#F9D978",
    "glow_outer": "#F5D799",
    "egg": "#D8A46F",
    "egg_light": "#F2C99B",
    "crack": "#6B371C",
    "broth": "#7C4424",
    "broth_light": "#A36037",
    "skin": "#F7CFA8",
    "skin_shade": "#E5B287",
    "blush": "#E88D72",
    "mouth_in": "#B8564B",
    "tongue": "#E37D73",
    "hair": "#4A2E1E",
    "hair_hi": "#6E4730",
    "apron": "#4A8B71",
    "apron_dark": "#356B55",
    "shirt": "#FFF6E5",
    "skewer": "#D4A359",
    "cup": "#F3DFC1",
    "cup_stripe": "#E07A5F",
    "steam": "#FFFDF7",
}

DEFAULT_PIXEL_HEX: Dict[str, str] = {
    "paper": "#D9C5A0",
    "outline": "#22162B",
    "night": "#1B1F3B",
    "night_mid": "#2C365E",
    "moon": "#FFE66D",
    "wall": "#D9C5A0",
    "wall_shade": "#BFA67A",
    "shelf": "#2EC4B6",
    "shelf_dark": "#1F7A73",
    "accent_coral": "#FF6B6B",
    "accent_berry": "#9B5DE5",
    "counter": "#BC7C43",
    "counter_dark": "#874F24",
    "steamer": "#C2C5CC",
    "steamer_dark": "#7D8491",
    "glass_tint": "#A8DADC",
    "glow": "#FF9F1C",
    "glow_inner": "#FFBF69",
    "glow_outer": "#E8AC65",
    "egg": "#E09F5A",
    "egg_light": "#FFD199",
    "crack": "#5C2C16",
    "broth": "#6E351A",
    "broth_light": "#994D26",
    "skin": "#FFCCA8",
    "skin_shade": "#E09E75",
    "blush": "#FF758F",
    "mouth_in": "#A8334C",
    "tongue": "#FF6B8B",
    "hair": "#3B2028",
    "hair_hi": "#5E3642",
    "apron": "#2A9D8F",
    "apron_dark": "#1D6F65",
    "shirt": "#F8F9FA",
    "skewer": "#E9C46A",
    "cup": "#F4E4C1",
    "cup_stripe": "#FF6B6B",
    "steam": "#F1FAEE",
}


@dataclass
class SpecConfig:
    fps: int = 24
    duration_sec: float = 8.0
    total_frames: int = 192
    width: int = 1280
    height: int = 720
    pixel_native_width: int = 320
    pixel_native_height: int = 180
    pixel_upscale: int = 4
    crayon_brush_size: int = 7
    line_boil_hold_frames: int = 4
    line_boil_amplitude_px: float = 1.8
    crayon_hatch_angle_deg: float = -22.0
    shot1_frames: Tuple[int, int] = (0, 59)
    shot2_frames: Tuple[int, int] = (60, 131)
    shot3_frames: Tuple[int, int] = (132, 191)
    subtitle_start_frame: int = 132
    subtitle_end_frame: int = 191
    subtitle_pos: Tuple[int, int] = (640, 636)
    crayon_font_name: str = "Iansui-Regular.ttf"
    crayon_font_size: int = 44
    pixel_font_name: str = "Cubic_11.ttf"
    pixel_font_size: int = 44
    rng_seed: int = 20261124
    raw_kv: Dict[str, str] = field(default_factory=dict)
    crayon_hex: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CRAYON_HEX))
    pixel_hex: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PIXEL_HEX))

    def palette_rgb(self, style: str) -> Dict[str, Tuple[int, int, int]]:
        src = self.crayon_hex if style == "crayon" else self.pixel_hex
        return {k: hex_to_rgb(v) for k, v in src.items()}


def _parse_palette_line(val: str, target: Dict[str, str]) -> None:
    for item in val.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            if v.startswith("#") and len(v) == 7:
                target[k] = v


def load_specs(specs_dir: Path = SPECS_DIR) -> SpecConfig:
    """Read all 99 spec markdown files under specs/ and parse key-value parameters."""
    cfg = SpecConfig()
    md_files = sorted(glob.glob(str(specs_dir / "*" / "*.md")))
    raw_kv: Dict[str, str] = {}

    for fpath in md_files:
        with open(fpath, "r", encoding="utf-8") as f:
            in_params = False
            for line in f:
                s = line.strip()
                if s.startswith("## 参数"):
                    in_params = True
                    continue
                if s.startswith("## ") and in_params:
                    in_params = False
                    continue
                if in_params and ":" in s and not s.startswith("#"):
                    k, v = s.split(":", 1)
                    raw_kv[k.strip()] = v.strip()

    cfg.raw_kv = raw_kv
    if "fps" in raw_kv:
        cfg.fps = int(raw_kv["fps"])
    if "duration_sec" in raw_kv:
        cfg.duration_sec = float(raw_kv["duration_sec"])
    if "total_frames" in raw_kv:
        cfg.total_frames = int(raw_kv["total_frames"])
    if "width" in raw_kv:
        cfg.width = int(raw_kv["width"])
    if "height" in raw_kv:
        cfg.height = int(raw_kv["height"])
    if "pixel_native_width" in raw_kv:
        cfg.pixel_native_width = int(raw_kv["pixel_native_width"])
    if "pixel_native_height" in raw_kv:
        cfg.pixel_native_height = int(raw_kv["pixel_native_height"])
    if "pixel_upscale" in raw_kv:
        cfg.pixel_upscale = int(raw_kv["pixel_upscale"])
    if "crayon_brush_size" in raw_kv:
        cfg.crayon_brush_size = int(raw_kv["crayon_brush_size"])
    if "line_boil_hold_frames" in raw_kv:
        cfg.line_boil_hold_frames = int(raw_kv["line_boil_hold_frames"])
    if "line_boil_amplitude_px" in raw_kv:
        cfg.line_boil_amplitude_px = float(raw_kv["line_boil_amplitude_px"])
    if "crayon_hatch_angle_deg" in raw_kv:
        cfg.crayon_hatch_angle_deg = float(raw_kv["crayon_hatch_angle_deg"])
    if "subtitle_start_frame" in raw_kv and "subtitle_end_frame" in raw_kv:
        cfg.subtitle_start_frame = int(raw_kv["subtitle_start_frame"])
        cfg.subtitle_end_frame = int(raw_kv["subtitle_end_frame"])
    if "subtitle_pos_x" in raw_kv and "subtitle_pos_y" in raw_kv:
        cfg.subtitle_pos = (int(raw_kv["subtitle_pos_x"]), int(raw_kv["subtitle_pos_y"]))
    if "crayon_font" in raw_kv:
        cfg.crayon_font_name = raw_kv["crayon_font"]
    if "crayon_font_size" in raw_kv:
        cfg.crayon_font_size = int(raw_kv["crayon_font_size"])
    if "pixel_font" in raw_kv:
        cfg.pixel_font_name = raw_kv["pixel_font"]
    if "pixel_font_size" in raw_kv:
        cfg.pixel_font_size = int(raw_kv["pixel_font_size"])
    if "rng_seed" in raw_kv:
        cfg.rng_seed = int(raw_kv["rng_seed"])

    if "style_a_palette" in raw_kv:
        _parse_palette_line(raw_kv["style_a_palette"], cfg.crayon_hex)
    if "style_b_palette" in raw_kv:
        _parse_palette_line(raw_kv["style_b_palette"], cfg.pixel_hex)

    # Validate zero #000000 in both palettes immediately
    _ = cfg.palette_rgb("crayon")
    _ = cfg.palette_rgb("pixel")
    return cfg


def ensure_font_path(font_name: str) -> Path:
    """Return local cached font path, downloading from GitHub API blob if needed."""
    FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = FONT_CACHE_DIR / font_name
    if target.exists() and target.stat().st_size > 100_000:
        return target
    url = FONT_BLOBS.get(font_name)
    if not url:
        raise FileNotFoundError(f"Font {font_name} not found in {FONT_CACHE_DIR}")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "makemovie-code-director",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    target.write_bytes(data)
    return target
