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

echo "Applying migrations..."
python manage.py migrate --noinput

# Detect the address other devices on the Wi-Fi should use. Termux's API knows
# the Wi-Fi interface directly; the socket fallback asks the kernel which source
# address it would use to reach the internet (no packets are sent, no
# permissions needed) and works where `ip` and `ifconfig` are restricted.
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

# Keep Android from sleeping the CPU while the server runs. Needs termux-api.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

LAN_IP="$(detect_lan_ip)"
echo
echo "  HireHorizon is starting."
echo "  On this phone:     http://localhost:${PORT}"
if [ -n "$LAN_IP" ]; then
    echo "  On other devices:  http://${LAN_IP}:${PORT}"
    # Django rejects hosts it hasn't been told about once DEBUG=False.
    export ALLOWED_HOSTS="${ALLOWED_HOSTS:-${LAN_IP},localhost,127.0.0.1}"
else
    echo "  On other devices:  could not detect this phone's Wi-Fi IP."
    echo "                     See 'Other devices can't reach it' in README.md."
fi
echo

exec python manage.py runserver "0.0.0.0:${PORT}"
