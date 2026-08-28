from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from .audio import VoiceAnalysis
from .model import ModelSettings
from .svg import RenderSettings, render_svg


def _voice_manifest(voice: VoiceAnalysis) -> dict[str, object]:
    active = voice.frequencies[voice.frequencies > 0]
    return {
        "name": voice.name,
        "sample_rate": voice.sample_rate,
        "source_duration_seconds": round(voice.duration, 4),
        "selection_seconds": [round(value, 4) for value in voice.selection],
        "analysis_frames": voice.frame_count,
        "frequency_range_hz": [
            round(float(active.min()), 2) if len(active) else None,
            round(float(active.max()), 2) if len(active) else None,
        ],
        "rms_before_equal_loudness_normalization": voice.rms_before_normalization,
        "isolated_representative_frequency_hz": round(voice.representative_frequency, 2),
        "isolated_signature_frequencies_hz": [
            round(float(value), 2) for value in voice.signature_frequencies if value > 0
        ],
    }


def build_export_zip(
    x: np.ndarray,
    y: np.ndarray,
    field: np.ndarray,
    voices: list[VoiceAnalysis],
    model_settings: ModelSettings,
    render_settings: RenderSettings,
) -> bytes:
    panel_count = len(voices)
    manifest = {
        "schema_version": 1,
        "dimensions_inches": {"width": 7, "panel_height": 7, "total_height": 7 * panel_count},
        "progression": "panel n combines voices 1 through n at equal pre-coupling loudness",
        "frequency_mapping": "logarithmic mapping from measured spectral peaks to square-plate modes",
        "model": asdict(model_settings),
        "render": asdict(render_settings),
        "voices": [_voice_manifest(voice) for voice in voices],
    }

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("master-paper.svg", render_svg(x, y, field, render_settings, medium="paper"))
        archive.writestr("master-wood.svg", render_svg(x, y, field, render_settings, medium="wood"))
        for panel in range(panel_count):
            crop = (panel, panel + 1)
            archive.writestr(
                f"panels/panel-{panel + 1}-paper.svg",
                render_svg(x, y, field, render_settings, medium="paper", crop=crop),
            )
            archive.writestr(
                f"panels/panel-{panel + 1}-wood.svg",
                render_svg(x, y, field, render_settings, medium="wood", crop=crop),
            )
    return output.getvalue()
