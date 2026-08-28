from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import streamlit.components.v1 as components

from cymatic_zine.audio import analyze_wav, wav_duration
from cymatic_zine.export import build_export_zip
from cymatic_zine.model import ModelSettings, build_field
from cymatic_zine.svg import DEFAULT_COLORS, RenderSettings, render_svg


def show_svg(svg: str, panel_count: int) -> None:
    document = svg.split("?>", 1)[-1]
    height = min(1100, max(500, panel_count * 420))
    components.html(
        f"""
        <style>
          html, body {{ margin: 0; background: #dedbd3; }}
          .preview {{ display: flex; justify-content: center; padding: 20px; }}
          .preview svg {{ display: block; width: min(100%, 700px); height: auto; }}
        </style>
        <div class="preview">{document}</div>
        """,
        height=height,
        scrolling=True,
    )


st.set_page_config(page_title="Cymatic Zine", layout="wide")
st.title("Cymatic Zine")
st.caption("Seven equal voices accumulating from blue to yellow across a 7 x 49 inch physical field.")

if "reflection_symmetry" not in ModelSettings.__dataclass_fields__:
    st.error("The server has an older model loaded. Stop Streamlit and start it again.")
    st.code(".venv/bin/python -m streamlit run app.py")
    st.stop()

uploads = st.file_uploader(
    "PCM WAV recordings, in final speaker order",
    type=["wav", "m4a"],
    accept_multiple_files=True,
    help="Upload one or two files for a prototype, then all seven for the final composition. WAV and M4A are supported.",
)
if len(uploads) > 7:
    st.error("Use no more than seven recordings.")
    st.stop()

with st.sidebar:
    st.header("Model")
    resolution = st.slider("Preview resolution", 100, 300, 180, 20)
    maximum_mode = st.slider("Maximum plate mode", 6, 18, 12)
    signature_modes = st.slider(
        "Number of frequencies per voice (n)",
        1,
        12,
        3,
        help="Select n distinct phrase-level spectral peaks for every speaker.",
    )
    temporal_influence = st.slider(
        "Top-to-bottom speech variation", 0.0, 0.3, 0.0, 0.02,
        disabled=signature_modes == 1,
    )
    damping = st.slider("Damping", 0.005, 0.08, 0.025, 0.005)
    coupling = st.slider("Fold coupling", 0.0, 0.3, 0.12, 0.01)
    reflection_symmetry = st.checkbox("Enforce bilateral and reflection symmetry", True)
    if reflection_symmetry:
        excitation_x = excitation_y = 0.5
        st.caption("The shared excitation is fixed at the plate center.")
    else:
        excitation_x = st.slider("Shared excitation X", 0.1, 0.9, 0.5, 0.01)
        excitation_y = st.slider("Shared excitation Y", 0.1, 0.9, 0.5, 0.01)
    seed = st.number_input("Variation seed", 0, 100000, 17)

    st.header("Fabrication")
    line_width = st.slider("Minimum line width (in)", 0.005, 0.04, 0.012, 0.001)
    minimum_gap = st.slider("Minimum gap (in)", 0.01, 0.12, 0.025, 0.005)
    base_contours = st.slider("Panel 1 contours", 1, 7, 1, 2)
    maximum_contours = st.slider("Final panel contours", 7, 21, 13, 2)
    hatch_threshold = st.slider("Wood hatch threshold", 0.1, 0.8, 0.42, 0.02)
    background = st.color_picker("Paper ground", "#f4efe4")
    st.subheader("Panel gradient")
    colors = tuple(
        st.color_picker(f"Panel {index + 1}", color, key=f"color-{index}")
        for index, color in enumerate(DEFAULT_COLORS)
    )

analyses = []
if uploads:
    st.subheader("Phrase selections")
    cleanup = st.slider("Conservative audio cleanup", 0.0, 1.0, 0.5, 0.05)
    for index, upload in enumerate(uploads):
        data = upload.getvalue()
        try:
            duration = wav_duration(data)
        except Exception as error:
            st.error(
                f"Could not read {upload.name}: {error} "
                "If this is M4A, run `python bootstrap.py` and restart Streamlit."
            )
            st.stop()
        if duration <= 0:
            st.error(f"Could not read {upload.name}: the file contains no audio samples.")
            st.stop()
        default_end = min(duration, 8.0)
        start, end = st.slider(
            f"{index + 1}. {upload.name}",
            0.0,
            float(duration),
            (0.0, float(default_end)),
            0.05,
            key=f"selection-{index}-{upload.name}",
        )
        st.audio(data, format="audio/wav")
        try:
            analyses.append(
                analyze_wav(
                    data,
                    upload.name,
                    start,
                    end,
                    cleanup=cleanup,
                    peak_count=max(12, signature_modes * 2),
                    signature_count=signature_modes,
                )
            )
            selected = analyses[-1].signature_frequencies
            selected = [f"{frequency:.1f} Hz" for frequency in selected if frequency > 0]
            st.caption(f"Selected {len(selected)} frequencies: {', '.join(selected)}")
        except ValueError as error:
            st.error(str(error))
            st.stop()

if analyses:
    model_settings = ModelSettings(
        resolution=resolution,
        maximum_mode=maximum_mode,
        damping=damping,
        coupling=coupling,
        excitation_x=excitation_x,
        excitation_y=excitation_y,
        signature_modes=signature_modes,
        temporal_influence=temporal_influence,
        reflection_symmetry=reflection_symmetry,
        seed=int(seed),
    )
    render_settings = RenderSettings(
        colors=colors,
        line_width_in=line_width,
        minimum_gap_in=minimum_gap,
        background=background,
        base_contours=base_contours,
        maximum_contours=maximum_contours,
        hatch_threshold=hatch_threshold,
    )
    with st.spinner("Analyzing voices and solving cumulative plate fields..."):
        x, y, field = build_field(analyses, model_settings)
        paper_svg = render_svg(x, y, field, render_settings, medium="paper")
        wood_svg = render_svg(x, y, field, render_settings, medium="wood")

    paper_tab, wood_tab = st.tabs(["Paper", "Wood"])
    with paper_tab:
        show_svg(paper_svg, len(analyses))
    with wood_tab:
        show_svg(wood_svg, len(analyses))

    export = build_export_zip(x, y, field, analyses, model_settings, render_settings)
    st.download_button(
        "Download fabrication package",
        export,
        file_name="cymatic-zine-fabrication.zip",
        mime="application/zip",
        type="primary",
    )
else:
    st.info("Upload at least one WAV recording to generate the first panel.")
