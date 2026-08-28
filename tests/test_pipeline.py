from __future__ import annotations

from io import BytesIO
import json
from xml.etree import ElementTree
from zipfile import ZipFile

import numpy as np

from cymatic_zine.audio import analyze_wav
from cymatic_zine.demo import synthetic_wav
from cymatic_zine.export import build_export_zip
from cymatic_zine.model import ModelSettings, build_field
from cymatic_zine.svg import RenderSettings, render_svg


def voices():
    return [
        analyze_wav(
            synthetic_wav((180.0, 540.0, 1200.0), 1.0),
            "one",
            0.0,
            1.0,
            analysis_frames=20,
            signature_count=3,
        ),
        analyze_wav(
            synthetic_wav((240.0, 720.0, 1600.0), 1.0),
            "two",
            0.0,
            1.0,
            analysis_frames=20,
            signature_count=3,
        ),
    ]


def test_analysis_tracks_source_frequencies():
    analysis = voices()[0]
    active = analysis.frequencies[analysis.frequencies > 0]
    assert analysis.frame_count == 20
    assert np.any(np.abs(active - 180.0) < 20.0)
    assert abs(analysis.representative_frequency - 180.0) < 20.0
    assert len(analysis.signature_frequencies[analysis.signature_frequencies > 0]) == 3
    assert analysis.rms_before_normalization > 0


def test_wav_duration_accepts_pcm_wav():
    from cymatic_zine.audio import wav_duration

    assert abs(wav_duration(synthetic_wav((180.0,), 1.0)) - 1.0) < 0.01


def test_empty_audio_is_rejected_before_duration_is_used():
    from cymatic_zine.audio import wav_duration

    try:
        wav_duration(b"not an audio file")
    except ValueError as error:
        assert "Could not decode audio" in str(error)
    else:
        raise AssertionError("invalid audio should be rejected")


def test_frequency_count_control_returns_requested_distinct_peaks():
    analysis = analyze_wav(
        synthetic_wav((180.0, 540.0, 1200.0), 1.0),
        "one",
        0.0,
        1.0,
        analysis_frames=20,
        peak_count=12,
        signature_count=3,
    )
    selected = analysis.signature_frequencies[analysis.signature_frequencies > 0]
    assert len(selected) == 3
    assert len(np.unique(selected)) == 3


def test_cumulative_field_is_deterministic_and_panel_sized():
    settings = ModelSettings(resolution=60, coupling=0.0)
    first = build_field(voices(), settings)
    second = build_field(voices(), settings)
    assert first[2].shape == (120, 60)
    np.testing.assert_allclose(first[2], second[2])
    assert not np.allclose(first[2][:60], first[2][60:])
    for panel in (first[2][:60], first[2][60:]):
        np.testing.assert_allclose(panel, np.fliplr(panel), atol=1e-12)
        np.testing.assert_allclose(panel, np.flipud(panel), atol=1e-12)


def test_svg_has_exact_physical_dimensions_and_progressive_gradient():
    x, y, field = build_field(voices(), ModelSettings(resolution=60))
    svg = render_svg(x, y, field, RenderSettings())
    assert 'width="7in" height="14in"' in svg
    assert "#3155a6" in svg
    assert "#2378ad" in svg
    assert svg.count("<path") > 5
    assert " C " in svg
    ElementTree.fromstring(svg)


def test_export_contains_master_panels_and_manifest():
    analyzed = voices()
    model = ModelSettings(resolution=60)
    render = RenderSettings()
    x, y, field = build_field(analyzed, model)
    payload = build_export_zip(x, y, field, analyzed, model, render)
    with ZipFile(BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert "master-paper.svg" in names
        assert "master-wood.svg" in names
        assert "panels/panel-2-paper.svg" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["dimensions_inches"]["total_height"] == 14
        assert len(manifest["voices"]) == 2
        assert manifest["voices"][0]["isolated_representative_frequency_hz"] > 0
