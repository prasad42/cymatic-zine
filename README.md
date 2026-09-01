# Cymatic Zine

A private production tool for translating seven recorded statements about hope
into a static, vertically arranged cymatic composition. Each 7 x 7 inch panel
contains the simultaneous merge of voices 1 through n, with nonlinear
interference creating a new pattern at each step. The complete seven-panel work
is 7 x 49 inches and can be exported for high-resolution printing or laser
engraving.

The model is cymatics-inspired rather than a prediction of one physical plate.
It uses documented square-plate modes, a shared central excitation point, one
isolated representative pitch from each voice, and coupled transitions between
panels. Exact vocal Hertz values are mapped logarithmically into a printable
modal range. Symmetry-compatible modes give each panel a cohesive bilateral and
reflection-symmetric cymatic pattern. Narrow fold zones connect the sequence.

## Requirements

- Python 3.11 or newer
- A current web browser for the local production interface
- NumPy 2.0 or newer for audio and field calculations
- ContourPy 1.3 or newer for fabrication paths
- Streamlit 1.42 or newer for the local interface
- ImageIO-FFmpeg 0.6 or newer for local M4A decoding
- Pytest 8.3 or newer for development tests

The Python packages are declared in `pyproject.toml` and installed inside the
project's `.venv`; they do not need to be installed globally. An internet
connection is required for the initial package installation.

## Install

The cross-platform bootstrap command creates `.venv` and installs the project
with its development dependencies:

```bash
python bootstrap.py
```

On systems where Python 3 is invoked as `python3`, use `python3 bootstrap.py`.
The `.venv` directory is local machine state and should not be copied between
laptops. Run the bootstrap command independently on each laptop instead.
After adding or changing dependencies, stop the running Streamlit process,
rerun the bootstrap command, and start Streamlit again.

Manual setup on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Manual setup on Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

```bash
.venv/bin/python -m streamlit run app.py
```

On Windows, run `.venv\Scripts\python.exe -m streamlit run app.py`.

Upload one to seven mono or stereo WAV or M4A recordings. M4A files are decoded
locally through the bundled FFmpeg runtime. Choose a phrase from
each waveform, choose `n` distinct phrase-level frequencies per voice with the
sidebar control, tune the fabrication controls, and download the ZIP export.
Recordings are processed locally and are not included in the export bundle.

For a deterministic command-line demonstration that needs no recordings:

```bash
.venv/bin/cymatic-zine demo --output demo-output
```

## Test

```bash
.venv/bin/python -m pytest
```

On Windows, run `.venv\Scripts\python.exe -m pytest`.

## Automatic Publishing

The repository is configured for agent-assisted publishing. The agent runs
tests, reviews the diff, commits completed changes, and pushes to `origin/main`.
SSH authentication must be available on the machine, and the private GitHub
repository must exist before the first push.

## Output

The export ZIP contains:

- A paper SVG master at exact physical dimensions
- A monochrome wood SVG master with progressive hatching
- One paper and one wood SVG per 7 x 7 inch panel
- A JSON manifest documenting selections, analysis, colors, and model settings

SVG is the fabrication master. A print shop can rasterize it at 600 DPI or
perform a printer-specific CMYK conversion without changing the geometry.

Before engraving the final work, use a material test to set minimum line width,
minimum gap, speed, and power for the actual laser and wood.
