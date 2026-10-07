"""Generates Resources/SilaiRahm.wav: the soft two-note chime of Silai Rahm notifications.

    python3 make_sound.py
"""
import math
import struct
import wave
from pathlib import Path

RATE = 44100
LENGTH = 1.25  # seconds


def bell(freq, start, t, decay=3.2):
    """A mallet-like tone: a fundamental with a few soft, faster-fading partials."""
    if t < start:
        return 0.0
    x = t - start
    attack = min(1.0, x / 0.006)
    tone = (math.sin(2 * math.pi * freq * x)
            + 0.32 * math.sin(2 * math.pi * freq * 2.0 * x) * math.exp(-x * 6)
            + 0.12 * math.sin(2 * math.pi * freq * 3.01 * x) * math.exp(-x * 9))
    return attack * tone * math.exp(-x * decay)


def main():
    frames = []
    for i in range(int(RATE * LENGTH)):
        t = i / RATE
        v = 0.5 * bell(659.25, 0.0, t) + 0.42 * bell(987.77, 0.13, t, decay=2.6)  # E5, then B5
        fade = min(1.0, (LENGTH - t) / 0.15)
        frames.append(max(-1.0, min(1.0, v * 0.55 * fade)))
    out = Path(__file__).parent / "Resources" / "SilaiRahm.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in frames))
    print(out)


if __name__ == "__main__":
    main()
