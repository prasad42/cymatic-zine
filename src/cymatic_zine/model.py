from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .audio import VoiceAnalysis


@dataclass(frozen=True)
class ModelSettings:
    resolution: int = 180
    minimum_mode: int = 1
    maximum_mode: int = 12
    damping: float = 0.025
    coupling: float = 0.12
    excitation_x: float = 0.5
    excitation_y: float = 0.5
    minimum_frequency: float = 80.0
    maximum_frequency: float = 5000.0
    signature_modes: int = 1
    temporal_influence: float = 0.0
    reflection_symmetry: bool = True
    seed: int = 17


def _mode_catalog(minimum: int, maximum: int) -> list[tuple[int, int]]:
    modes = [(m, n) for m in range(1, maximum + 1) for n in range(1, maximum + 1)]
    modes.sort(key=lambda mode: (mode[0] ** 2 + mode[1] ** 2, mode[0], mode[1]))
    return [mode for mode in modes if max(mode) >= minimum]


def _symmetric_mode_catalog(minimum: int, maximum: int) -> list[tuple[int, int]]:
    return [
        mode
        for mode in _mode_catalog(minimum, maximum)
        if mode[0] % 2 == 1 and mode[1] % 2 == 1 and mode[0] <= mode[1]
    ]


def _frequency_to_mode(
    frequency: float,
    modes: list[tuple[int, int]],
    minimum_frequency: float,
    maximum_frequency: float,
) -> tuple[int, int]:
    normalized = (math.log(max(frequency, minimum_frequency)) - math.log(minimum_frequency)) / (
        math.log(maximum_frequency) - math.log(minimum_frequency)
    )
    index = int(np.clip(round(normalized * (len(modes) - 1)), 0, len(modes) - 1))
    return modes[index]


def _voice_modes(
    voice: VoiceAnalysis, settings: ModelSettings, modes: list[tuple[int, int]]
) -> list[tuple[tuple[int, int], float]]:
    """Map the selected phrase frequencies to distinct plate modes."""
    selected: list[tuple[tuple[int, int], float]] = []
    used: set[tuple[int, int]] = set()
    frequencies = voice.signature_frequencies[: settings.signature_modes]
    weights = voice.signature_weights[: settings.signature_modes]
    for frequency, weight in zip(frequencies, weights, strict=True):
        if frequency <= 0 or weight <= 0:
            continue
        mapped = _frequency_to_mode(
            float(frequency), modes, settings.minimum_frequency, settings.maximum_frequency
        )
        if mapped in used:
            mapped_index = modes.index(mapped)
            available = [index for index, mode in enumerate(modes) if mode not in used]
            if not available:
                continue
            mapped = modes[min(available, key=lambda index: abs(index - mapped_index))]
        used.add(mapped)
        selected.append((mapped, float(weight)))
    if not selected:
        selected.append(
            (
                _frequency_to_mode(
                    voice.representative_frequency,
                    modes,
                    settings.minimum_frequency,
                    settings.maximum_frequency,
                ),
                1.0,
            )
        )
    total = sum(weight for _, weight in selected)
    return [(mode, weight / total) for mode, weight in selected]


def _panel_field(
    voices: list[VoiceAnalysis], settings: ModelSettings, x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    modes = (
        _symmetric_mode_catalog(settings.minimum_mode, settings.maximum_mode)
        if settings.reflection_symmetry
        else _mode_catalog(settings.minimum_mode, settings.maximum_mode)
    )
    field = np.zeros((len(y), len(x)), dtype=np.float64)

    for voice in voices:
        voice_modes = _voice_modes(voice, settings, modes)
        voice_field = np.zeros_like(field)
        for mode, weight in voice_modes:
            m, n = mode
            excitation = math.sin(m * math.pi * settings.excitation_x) * math.sin(
                n * math.pi * settings.excitation_y
            )
            attenuation = 1.0 / (1.0 + settings.damping * (m * m + n * n))
            first = np.sin(m * math.pi * x)[None, :] * np.sin(n * math.pi * y)[:, None]
            if m == n:
                plate_mode = first
            else:
                swapped = np.sin(n * math.pi * x)[None, :] * np.sin(m * math.pi * y)[:, None]
                plate_mode = (first + swapped) / math.sqrt(2.0)
            voice_field += weight * excitation * attenuation * plate_mode
        field += voice_field

    # Equal-loudness inputs contribute equally; sqrt scaling prevents later panels
    # from gaining amplitude merely because more voices are present.
    if voices:
        field /= math.sqrt(len(voices))
    if settings.reflection_symmetry:
        field = (field + np.fliplr(field) + np.flipud(field) + np.flip(field)) / 4.0
    return field


def _smooth_seams(field: np.ndarray, panel_height: int, coupling: float) -> np.ndarray:
    if coupling <= 0:
        return field
    result = field.copy()
    radius = max(2, int(panel_height * min(coupling, 0.3)))
    for seam in range(panel_height, len(field), panel_height):
        top = max(0, seam - radius)
        bottom = min(len(field), seam + radius)
        before = field[max(0, seam - radius - 1)]
        after = field[min(len(field) - 1, seam + radius)]
        blend = np.linspace(0.0, 1.0, bottom - top)[:, None]
        smooth = before[None, :] * (1.0 - blend) + after[None, :] * blend
        strength = math.sin(min(coupling / 0.3, 1.0) * math.pi / 2.0)
        result[top:bottom] = result[top:bottom] * (1.0 - strength) + smooth * strength
    return result


def build_field(
    voices: list[VoiceAnalysis], settings: ModelSettings = ModelSettings()
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not voices:
        raise ValueError("At least one analyzed voice is required")
    panel_height = settings.resolution
    x = np.linspace(0.0, 1.0, settings.resolution)
    local_y = (np.arange(panel_height) + 0.5) / panel_height
    panels = [_panel_field(voices[: index + 1], settings, x, local_y) for index in range(len(voices))]
    field = _smooth_seams(np.vstack(panels), panel_height, settings.coupling)

    for panel_index in range(len(voices)):
        section = slice(panel_index * panel_height, (panel_index + 1) * panel_height)
        scale = np.quantile(np.abs(field[section]), 0.98)
        if scale > 1e-12:
            field[section] /= scale
    y = (np.arange(len(field)) + 0.5) / panel_height
    return x, y, field
