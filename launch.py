from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def running_in_wsl() -> bool:
    try:
        version = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def requested_port() -> int:
    arguments = sys.argv[1:]
    for index, argument in enumerate(arguments):
        if argument == "--server.port" and index + 1 < len(arguments):
            return int(arguments[index + 1])
        if argument.startswith("--server.port="):
            return int(argument.partition("=")[2])
    return 8501


def open_wsl_browser(url: str) -> None:
    candidates = ["explorer.exe", "/mnt/c/Windows/explorer.exe"]
    for candidate in candidates:
        if candidate != candidates[0] and not Path(candidate).exists():
            continue
        if candidate == candidates[0] and shutil.which(candidate) is None:
            continue
        try:
            subprocess.Popen(
                [candidate, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            continue
        return
    print(f"Open this URL in a browser: {url}")


def wait_for_server(process: subprocess.Popen[bytes], port: int) -> bool:
    deadline = time.monotonic() + 30
    while process.poll() is None and time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.2)
    return process.poll() is None


def main() -> int:
    python = venv_python()
    if not python.exists():
        subprocess.run([sys.executable, str(ROOT / "bootstrap.py")], cwd=ROOT, check=True)
        python = venv_python()

    if not python.exists():
        print(f"Could not find the project Python interpreter at {python}", file=sys.stderr)
        return 1

    arguments = ["run"]
    if running_in_wsl():
        arguments.extend(["--server.headless", "true"])
    arguments.extend([str(ROOT / "app.py"), *sys.argv[1:]])
    command = [str(python), "-m", "streamlit", *arguments]

    if not running_in_wsl():
        return subprocess.run(command, cwd=ROOT).returncode

    process = subprocess.Popen(command, cwd=ROOT)
    if wait_for_server(process, requested_port()):
        open_wsl_browser(f"http://localhost:{requested_port()}")
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
