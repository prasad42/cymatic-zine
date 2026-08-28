# Cymatic Zine Agent Guide

## Setup

Run `python bootstrap.py` when `.venv` is absent or dependencies change. Use the
interpreter inside `.venv` for every command. On Unix it is `.venv/bin/python`;
on Windows it is `.venv\Scripts\python.exe`.

## Verification

Run `.venv/bin/python -m pytest` on Unix or
`.venv\Scripts\python.exe -m pytest` on Windows after changing numerical,
audio, SVG, export, or packaging code. The deterministic two-voice demo is the
fixture when private recordings are unavailable.

## Publishing

The project owner requested automatic publishing. After completing a code
change, run the relevant tests, inspect the staged diff, create a concise Git
commit, and push it to `origin/main`. Use the repository's configured Git
identity. Keep generated outputs, `.venv`, recordings, credentials, and other
machine-local files out of commits; `.gitignore` is the first check. If the
remote is unavailable, keep the commit locally and report the push blocker.

The remote is `git@github.com:prasad42/cymatic-zine.git`. Push only after tests
pass and the commit contains the intended files.

## Product Invariants

- The final master has seven vertical 7 x 7 inch panels and measures 7 x 49 inches.
- Panel `n` combines voices `1..n` at equal pre-coupling loudness.
- Every voice uses one shared central excitation position in the symmetric model.
- Panel cores have horizontal and vertical reflection symmetry; fold zones may transition.
- Density and saturation increase from panel 1 through panel 7.
- Outputs are static fabrication files; audio and animation are not public artifacts.
- Preserve deterministic output and record model settings in `manifest.json`.
- Keep source recordings local and exclude them from export packages.
