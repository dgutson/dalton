#!/data/data/com.termux/files/usr/bin/bash
# Serve Dalton on loopback only. http://localhost is a secure origin in Chrome,
# which is what getUserMedia requires — a file:// page cannot open the camera.
cd "$(dirname "$0")" || exit 1
PORT="${1:-8080}"
command -v termux-wake-lock >/dev/null && termux-wake-lock
trap 'command -v termux-wake-unlock >/dev/null && termux-wake-unlock' EXIT
exec python3 serve.py "$PORT"
