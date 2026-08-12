#!/usr/bin/env bash
# Start HireHorizon on Termux (or any local machine) and serve it on the LAN.
# Usage: bash run.sh
set -e

cd "$(dirname "$0")"

PORT="${PORT:-8000}"

if [ ! -d .venv ]; then
    echo "Creating virtualenv..."
    python -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip wheel
pip install -q -r requirements-termux.txt

# Keep Android from sleeping the CPU while the server runs. Needs termux-api.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo "Serving on http://0.0.0.0:${PORT} (open http://<phone-ip>:${PORT} from another device)"
exec gunicorn -b "0.0.0.0:${PORT}" -w 1 main:app
