#!/usr/bin/env bash
# Start HireHorizon on Termux (or any local machine) and serve it on the LAN.
# Usage: bash run.sh
#
# First run creates .venv and a .env holding a generated SECRET_KEY, then
# migrates, collects static files and starts the server bound to 0.0.0.0 so
# other devices on the same Wi-Fi can reach it.
set -e

cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# Termux ships `python`; some other systems only have `python3`.
if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo "Python not found. On Termux: pkg install python" >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtualenv..."
    "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements-termux.txt

# Generate a persistent SECRET_KEY on first run. Without it the app would fall
# back to a random key each restart, logging everyone out. DEBUG is off by
# default: this server is reachable by every device on your Wi-Fi, and with
# DEBUG on Django shows a full traceback (settings included) on any error.
if [ ! -f .env ]; then
    echo "Creating .env with a generated SECRET_KEY..."
    {
        echo "SECRET_KEY=$(python manage.py generate_secret_key)"
        echo "DEBUG=False"
    } > .env
fi

echo "Applying migrations..."
python manage.py migrate --noinput

# Detect the address other devices should use. Termux's API knows the Wi-Fi
# interface directly; the socket fallback asks the kernel which source address
# it would use to reach the internet (no packets sent, no permissions needed)
# and works where `ip` and `ifconfig` are restricted, as they are on Android.
detect_lan_ip() {
    if command -v termux-wifi-connectioninfo >/dev/null 2>&1; then
        ip=$(termux-wifi-connectioninfo 2>/dev/null |
            sed -n 's/.*"ip"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        case "$ip" in
            ""|"<unknown>"|"0.0.0.0") ;;
            *) echo "$ip"; return ;;
        esac
    fi
    python - <<'PY' 2>/dev/null
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
except OSError:
    pass
finally:
    s.close()
PY
}

LAN_IP="$(detect_lan_ip)"

# With DEBUG=False Django rejects any Host header it wasn't told about.
if [ -z "${ALLOWED_HOSTS:-}" ]; then
    if [ -n "$LAN_IP" ]; then
        export ALLOWED_HOSTS="${LAN_IP},localhost,127.0.0.1"
    else
        export ALLOWED_HOSTS="localhost,127.0.0.1"
    fi
fi

# WhiteNoise serves these; with DEBUG=False they must exist before first request.
echo "Collecting static files..."
python manage.py collectstatic --noinput >/dev/null

# Keep Android from sleeping the CPU while the server runs. Needs termux-api.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo
echo "  HireHorizon is starting."
echo "  On this phone:     http://localhost:${PORT}"
if [ -n "$LAN_IP" ]; then
    echo "  On other devices:  http://${LAN_IP}:${PORT}"
else
    echo "  On other devices:  could not detect this phone's Wi-Fi IP."
    echo "                     See 'Other devices can't reach it' in README.md."
fi
echo "  Admin:             http://localhost:${PORT}/admin/"
echo
echo "  No account yet?  Stop this (Ctrl+C), then run:"
echo "    source .venv/bin/activate && python manage.py createsuperuser"
echo

exec python manage.py runserver "0.0.0.0:${PORT}"
