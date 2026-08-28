from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
import subprocess
import wave

import imageio_ffmpeg
import numpy as np


@dataclass(frozen=True)
class VoiceAnalysis:
    name: str
    sample_rate: int
    duration: float
    selection: tuple[float, float]
    frequencies: np.ndarray
    weights: np.ndarray
    voicedness: np.ndarray
    rms_before_normalization: float
    representative_frequency: float
    signature_frequencies: np.ndarray
    signature_weights: np.ndarray

    @property
    def frame_count(self) -> int:
        return int(self.frequencies.shape[0])


def _is_readable_wav(data: bytes) -> bool:
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return False
    try:
        with wave.open(BytesIO(data), "rb"):
            return True
    except wave.Error:
        return False


def _as_wav(data: bytes) -> bytes:
    if _is_readable_wav(data):
        return data
    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        converted = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "pipe:1",
            ],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.decode(errors="replace") if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise ValueError(f"Could not decode audio. Upload PCM WAV or a supported M4A file. {detail}") from error
    return converted.stdout


def wav_duration(data: bytes) -> float:
    if _is_readable_wav(data):
        with wave.open(BytesIO(data), "rb") as source:
            return source.getnframes() / source.getframerate()
    audio, sample_rate = _decode_pcm(data)
    if not len(audio):
        raise ValueError("The file contains no decodable audio samples")
    return len(audio) / sample_rate


def _decode_pcm(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(BytesIO(_as_wav(data)), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())

    if sample_width == 1:
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float64)
        audio = (audio - 128.0) / 128.0
    elif sample_width == 2:
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        values = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        audio = values.astype(np.float64) / 8388608.0
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"Unsupported PCM sample width: {sample_width * 8} bits")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sample_rate


def _high_pass(audio: np.ndarray, sample_rate: int, cutoff: float) -> np.ndarray:
    if cutoff <= 0 or len(audio) < 2:
        return audio.copy()
    dt = 1.0 / sample_rate
    rc = 1.0 / (2.0 * math.pi * cutoff)
    alpha = rc / (rc + dt)
    result = np.empty_like(audio)
    result[0] = audio[0]
    for index in range(1, len(audio)):
        result[index] = alpha * (result[index - 1] + audio[index] - audio[index - 1])
    return result


def _spectral_peaks(
    frame: np.ndarray,
    sample_rate: int,
    peak_count: int,
    minimum_frequency: float,
    maximum_frequency: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    spectrum = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
    bins = np.fft.rfftfreq(len(frame), 1.0 / sample_rate)
    valid = (bins >= minimum_frequency) & (bins <= maximum_frequency)
    valid_indices = np.flatnonzero(valid)
    if len(valid_indices) < 3:
        return np.zeros(peak_count), np.zeros(peak_count), 0.0

    local = valid_indices[1:-1]
    maxima = local[(spectrum[local] >= spectrum[local - 1]) & (spectrum[local] > spectrum[local + 1])]
    if not len(maxima):
        maxima = valid_indices[np.argsort(spectrum[valid_indices])[-peak_count:]]
    strongest = maxima[np.argsort(spectrum[maxima])[-peak_count:]][::-1]

    frequencies = np.zeros(peak_count, dtype=np.float64)
    weights = np.zeros(peak_count, dtype=np.float64)
    frequencies[: len(strongest)] = bins[strongest]
    weights[: len(strongest)] = spectrum[strongest]
    if weights.sum() > 0:
        weights /= weights.sum()

    band = spectrum[valid_indices] + 1e-12
    flatness = float(np.exp(np.mean(np.log(band))) / np.mean(band))
    voicedness = float(np.clip(1.0 - flatness, 0.0, 1.0))
    # Breaths and unvoiced consonants remain present, but at reduced influence.
    weights *= 0.35 + 0.65 * voicedness
    return frequencies, weights, voicedness


def _phrase_signature(
    frequencies: np.ndarray,
    weights: np.ndarray,
    count: int,
) -> tuple[np.ndarray, np.ndarray]:
    candidates = [
        (float(frequency), float(weight))
        for frequency, weight in zip(frequencies.ravel(), weights.ravel(), strict=True)
        if frequency > 0 and weight > 0
    ]
    candidates.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[float, float]] = []
    for frequency, weight in candidates:
        # The same peak appears in many adjacent frames. Keep distinct peaks at
        # the phrase level instead of counting those repeated observations.
        if any(abs(frequency - other) <= max(12.0, other * 0.035) for other, _ in selected):
            continue
        selected.append((frequency, weight))
        if len(selected) == count:
            break

    result_frequencies = np.zeros(count, dtype=np.float64)
    result_weights = np.zeros(count, dtype=np.float64)
    if selected:
        result_frequencies[: len(selected)] = [frequency for frequency, _ in selected]
        result_weights[: len(selected)] = [weight for _, weight in selected]
        result_weights /= result_weights.sum()
    return result_frequencies, result_weights


def analyze_wav(
    data: bytes,
    name: str,
    start: float,
    end: float,
    *,
    cleanup: float = 0.5,
    peak_count: int = 8,
    signature_count: int = 1,
    analysis_frames: int = 72,
    minimum_frequency: float = 80.0,
    maximum_frequency: float = 5000.0,
) -> VoiceAnalysis:
    audio, sample_rate = _decode_pcm(data)
    full_duration = len(audio) / sample_rate
    start = float(np.clip(start, 0.0, full_duration))
    end = float(np.clip(end, start, full_duration))
    if end - start < 0.1:
        raise ValueError("Select at least 0.1 seconds of audio")

    selected = audio[int(start * sample_rate) : int(end * sample_rate)]
    selected = selected - np.mean(selected)
    selected = _high_pass(selected, sample_rate, 45.0 + 45.0 * cleanup)
    rms = float(np.sqrt(np.mean(selected**2)))
    if rms < 1e-8:
        raise ValueError(f"{name} contains no usable audio in the selected range")
    selected = selected / rms

    frame_size = min(2048, max(512, 2 ** int(math.log2(max(512, len(selected) // 24)))))
    centers = np.linspace(frame_size // 2, max(frame_size // 2, len(selected) - frame_size // 2), analysis_frames)
    frequencies = np.zeros((analysis_frames, peak_count), dtype=np.float64)
    weights = np.zeros_like(frequencies)
    voicedness = np.zeros(analysis_frames, dtype=np.float64)
    for frame_index, center in enumerate(centers.astype(int)):
        left = center - frame_size // 2
        right = left + frame_size
        frame = np.zeros(frame_size, dtype=np.float64)
        source_left = max(0, left)
        source_right = min(len(selected), right)
        frame[source_left - left : source_right - left] = selected[source_left:source_right]
        frequencies[frame_index], weights[frame_index], voicedness[frame_index] = _spectral_peaks(
            frame, sample_rate, peak_count, minimum_frequency, maximum_frequency
        )

    signature_frequencies, signature_weights = _phrase_signature(
        frequencies, weights, max(1, signature_count)
    )

    pitch_mask = (frequencies >= 70.0) & (frequencies <= 420.0) & (weights > 0)
    pitch_frequencies = frequencies[pitch_mask]
    pitch_weights = weights[pitch_mask]
    if len(pitch_frequencies):
        order = np.argsort(pitch_frequencies)
        sorted_frequencies = pitch_frequencies[order]
        cumulative = np.cumsum(pitch_weights[order])
        representative_frequency = float(
            sorted_frequencies[np.searchsorted(cumulative, cumulative[-1] * 0.5)]
        )
    else:
        strongest = np.unravel_index(np.argmax(weights), weights.shape)
        representative_frequency = float(frequencies[strongest])

    return VoiceAnalysis(
        name=name,
        sample_rate=sample_rate,
        duration=full_duration,
        selection=(start, end),
        frequencies=frequencies,
        weights=weights,
        voicedness=voicedness,
        rms_before_normalization=rms,
        representative_frequency=representative_frequency,
        signature_frequencies=signature_frequencies,
        signature_weights=signature_weights,
    )
