#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    exec python3 launch.py "$@"
fi

if command -v python >/dev/null 2>&1; then
    exec python launch.py "$@"
fi

printf '%s\n' "Python 3 is not installed. Install Python 3.11 or newer, then run this launcher again." >&2
exit 1
