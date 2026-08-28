from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def main() -> None:
    if not venv_python().exists():
        print(f"Creating virtual environment at {VENV}")
        venv.EnvBuilder(with_pip=True).create(VENV)

    python = venv_python()
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-e", ".[dev]"],
        cwd=ROOT,
        check=True,
    )
    print("Environment ready.")
    print(f"Run the app with: {python} -m streamlit run app.py")
    print(f"Run tests with:   {python} -m pytest")


if __name__ == "__main__":
    main()
