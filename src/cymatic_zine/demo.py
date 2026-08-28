from __future__ import annotations

from io import BytesIO
import math
import wave

import numpy as np


def synthetic_wav(frequencies: tuple[float, ...], duration: float = 4.0, sample_rate: int = 16000) -> bytes:
    time = np.arange(round(duration * sample_rate)) / sample_rate
    envelope = np.sin(np.pi * np.clip(time / duration, 0.0, 1.0)) ** 0.4
    signal = sum(
        np.sin(2.0 * math.pi * frequency * time + index * 0.3) / (index + 1)
        for index, frequency in enumerate(frequencies)
    )
    signal *= envelope / max(np.max(np.abs(signal)), 1e-12) * 0.8
    pcm = np.round(signal * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm.tobytes())
    return output.getvalue()
