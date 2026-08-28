from __future__ import annotations

import argparse
from pathlib import Path

from .audio import analyze_wav
from .demo import synthetic_wav
from .export import build_export_zip
from .model import ModelSettings, build_field
from .svg import RenderSettings, render_svg


def _demo(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    sources = [
        ("Voice 1", (180.0, 520.0, 1280.0)),
        ("Voice 2", (230.0, 690.0, 1540.0)),
    ]
    voices = [
        analyze_wav(synthetic_wav(frequencies), name, 0.0, 4.0, signature_count=3)
        for name, frequencies in sources
    ]
    model = ModelSettings()
    render = RenderSettings()
    x, y, field = build_field(voices, model)
    (output / "prototype-paper.svg").write_text(render_svg(x, y, field, render, medium="paper"))
    (output / "prototype-wood.svg").write_text(render_svg(x, y, field, render, medium="wood"))
    (output / "prototype.zip").write_bytes(build_export_zip(x, y, field, voices, model, render))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cymatic zine fabrication files")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="generate a deterministic two-voice prototype")
    demo.add_argument("--output", type=Path, default=Path("demo-output"))
    arguments = parser.parse_args()
    if arguments.command == "demo":
        _demo(arguments.output)


if __name__ == "__main__":
    main()
