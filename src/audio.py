"""Procedural 44.1kHz stereo soundtrack and synced SFX generator (specs/09-audio).
- Version A (crayon): Warm celesta / wooden music-box melody + soft steam & foley
- Version B (pixel):  16-bit retro console pulse/triangle chiptune + retro SFX
"""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import List, Tuple

import numpy as np

SAMPLE_RATE = 44100


def _midi_to_hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


# Shared cozy midnight melody (F major pentatonic / warm seventh intervals)
# (start_sec, dur_sec, midi_note, velocity)
MELODY_NOTES: List[Tuple[float, float, int, float]] = [
    # Shot 1 [0.0 - 2.5s]: Quiet midnight store & simmering tea egg
    (0.10, 0.65, 65, 0.34),  # F4
    (0.65, 0.65, 69, 0.32),  # A4
    (1.20, 0.70, 72, 0.36),  # C5
    (1.80, 0.75, 76, 0.34),  # E5 (warm Fmaj7)
    # Shot 2 [2.5 - 5.5s]: Walk in, reach, hesitate [4.1-4.7s], warm smile [4.75s]
    (2.55, 0.45, 74, 0.33),  # D5
    (3.02, 0.45, 72, 0.31),  # C5
    (3.52, 0.55, 69, 0.34),  # A4 (reaching...)
    (4.18, 0.42, 70, 0.25),  # Bb4 (gentle hesitation pause!)
    (4.76, 0.40, 72, 0.38),  # C5 (smile blooms!)
    (5.10, 0.42, 76, 0.40),  # E5
    # Shot 3 [5.5 - 8.0s]: Holding up the tea egg — "最後一隻，係我嘅。"
    (5.52, 0.45, 77, 0.44),  # F5
    (5.95, 0.45, 74, 0.38),  # D5
    (6.40, 0.48, 72, 0.38),  # C5
    (6.88, 0.95, 77, 0.45),  # F5 warm resolving hold
]

BASS_NOTES: List[Tuple[float, float, int, float]] = [
    (0.10, 2.30, 53, 0.24),  # F3
    (2.55, 1.50, 50, 0.22),  # D3
    (4.15, 1.30, 46, 0.20),  # Bb2
    (5.52, 1.30, 48, 0.24),  # C3
    (6.85, 1.05, 53, 0.28),  # F3
]


def synthesize_audio(style: str, out_wav: Path, duration_sec: float = 8.0) -> Path:
    n_samples = int(round(duration_sec * SAMPLE_RATE))
    t = np.arange(n_samples, dtype=np.float32) / float(SAMPLE_RATE)
    left = np.zeros(n_samples, dtype=np.float32)
    right = np.zeros(n_samples, dtype=np.float32)
    rng = np.random.default_rng(20261124)

    def add_tone(start: float, dur: float, freq: float, amp: float, pan: float = 0.0, mode: str = "bell") -> None:
        i0 = max(0, int(start * SAMPLE_RATE))
        i1 = min(n_samples, int((start + dur) * SAMPLE_RATE))
        if i1 <= i0:
            return
        lt = np.arange(i1 - i0, dtype=np.float32) / float(SAMPLE_RATE)
        if mode == "bell":
            # Warm music-box / wooden celesta overtones
            env = np.minimum(1.0, lt / 0.012) * np.exp(-lt * 3.2)
            sig = (
                0.72 * np.sin(2.0 * math.pi * freq * lt)
                + 0.22 * np.sin(2.0 * math.pi * freq * 2.0 * lt) * np.exp(-lt * 5.0)
                + 0.06 * np.sin(2.0 * math.pi * freq * 3.0 * lt) * np.exp(-lt * 8.0)
            ) * env
        elif mode == "warm_bass":
            env = np.minimum(1.0, lt / 0.03) * np.exp(-lt * 1.4) * np.minimum(1.0, (dur - lt) / 0.05)
            sig = (0.85 * np.sin(2.0 * math.pi * freq * lt) + 0.15 * np.sin(4.0 * math.pi * freq * lt)) * env
        elif mode == "pulse25":
            # Authentic 16-bit 25% duty-cycle pulse wave (band-limited via harmonics)
            env = np.minimum(1.0, lt / 0.006) * np.exp(-lt * 2.8) * np.minimum(1.0, (dur - lt) / 0.02)
            phase = (freq * lt) % 1.0
            raw_p = np.where(phase < 0.25, 0.65, -0.22).astype(np.float32)
            sig = raw_p * env
        elif mode == "triangle":
            # Classic 16-bit quantized triangle bass
            env = np.minimum(1.0, lt / 0.008) * np.minimum(1.0, (dur - lt) / 0.03)
            phase = (freq * lt) % 1.0
            tri = 4.0 * np.abs(phase - 0.5) - 1.0
            tri = np.round(tri * 7.0) / 7.0
            sig = tri.astype(np.float32) * env
        else:
            sig = np.sin(2.0 * math.pi * freq * lt)

        l_gain = amp * math.sqrt(0.5 * (1.0 - pan))
        r_gain = amp * math.sqrt(0.5 * (1.0 + pan))
        left[i0:i1] += sig * l_gain
        right[i0:i1] += sig * r_gain

    lead_mode = "bell" if style == "crayon" else "pulse25"
    bass_mode = "warm_bass" if style == "crayon" else "triangle"

    for st, dur, midi, vel in MELODY_NOTES:
        add_tone(st, dur, _midi_to_hz(midi), vel * 0.42, pan=0.12, mode=lead_mode)

    for st, dur, midi, vel in BASS_NOTES:
        add_tone(st, dur, _midi_to_hz(midi), vel * 0.36, pan=-0.12, mode=bass_mode)

    # Synced Foley & Action Cues!
    # 1) Gentle simmering steam ambience (strongest in Shot 1, subtle throughout)
    white = rng.standard_normal(n_samples).astype(np.float32)
    # Simple moving-average lowpass for soft cozy steam hiss
    kernel = np.ones(18 if style == "crayon" else 8, dtype=np.float32)
    kernel /= kernel.sum()
    hiss = np.convolve(white, kernel, mode="same")
    steam_env = np.where(t < 2.5, 0.028, 0.014) * (0.85 + 0.15 * np.sin(t * 4.5))
    left += hiss * steam_env * 0.8
    right += hiss * steam_env * 1.1

    # 2) Two soft footsteps when clerk walks in [2.68s, 3.08s]
    for step_t in (2.68, 3.08):
        add_tone(step_t, 0.08, 135.0 if style == "crayon" else 160.0, 0.16, pan=-0.25, mode=bass_mode)

    # 3) Tiny hesitation tick at [4.22s]
    add_tone(4.22, 0.09, _midi_to_hz(79), 0.12, pan=0.0, mode=lead_mode)

    # 4) Warm sparkle chime on smile [4.78s] and proud tea-egg pickup [5.52s]
    for idx_arp, semi in enumerate((65, 69, 72, 77, 81)):
        add_tone(5.50 + idx_arp * 0.045, 0.32, _midi_to_hz(semi), 0.14, pan=0.18, mode=lead_mode)

    # Master soft fade-in / fade-out and -3 dBFS peak normalization
    fade_in = np.clip(t / 0.08, 0.0, 1.0)
    fade_out = np.clip((duration_sec - t) / 0.18, 0.0, 1.0)
    fade = fade_in * fade_out
    left *= fade
    right *= fade

    peak = max(1e-5, float(max(np.max(np.abs(left)), np.max(np.abs(right)))))
    target_peak = 0.68  # approx -3.3 dBFS
    scale = min(1.8, target_peak / peak)
    stereo = np.stack([left * scale, right * scale], axis=1)
    pcm16 = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    return out_wav
