from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def main() -> int:
    python = venv_python()
    if not python.exists():
        subprocess.run([sys.executable, str(ROOT / "bootstrap.py")], cwd=ROOT, check=True)
        python = venv_python()

    if not python.exists():
        print(f"Could not find the project Python interpreter at {python}", file=sys.stderr)
        return 1

    command = [
        str(python),
        "-m",
        "streamlit",
        "run",
        str(ROOT / "app.py"),
        *sys.argv[1:],
    ]
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
