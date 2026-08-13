#!/usr/bin/env bash
# Expose HireHorizon to the public Internet from this phone, via a Cloudflare
# Tunnel. No account, no signup, no inbound ports opened on your router.
#
# What this does:
#   1. Sets up the venv and .env exactly like run.sh (safe to run standalone).
#   2. Downloads the cloudflared binary if it isn't already present.
#   3. Starts Django behind gunicorn -- NOT the "runserver" dev server, which
#      Django's own docs say not to use for anything reachable by the public.
#   4. Starts a Cloudflare "quick tunnel" and prints the public HTTPS URL.
#
# The URL looks like https://some-random-words.trycloudflare.com and is free,
# but NOT permanent -- you get a different one every time you run this
# script. If you want a URL that never changes, see "Public access with your
# own domain" in README.md.
#
# Usage: bash tunnel.sh
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

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

if [ ! -f .env ]; then
    echo "Creating .env with a generated SECRET_KEY..."
    {
        echo "SECRET_KEY=$(python manage.py generate_secret_key)"
        echo "DEBUG=False"
    } > .env
fi

# --- cloudflared -------------------------------------------------------
CLOUDFLARED=""

# 1. Already on PATH (a prior `pkg install cloudflared`, or this script's own
#    earlier run) -- always the best option, since it's a binary the package
#    manager already knows is built correctly for this device.
if command -v cloudflared >/dev/null 2>&1; then
    CLOUDFLARED="$(command -v cloudflared)"
fi

# 2. Under Termux, try installing the real package before ever touching a
#    hand-downloaded binary. Termux packages are built specifically for
#    Android's Bionic libc and its execve() restrictions; a generic
#    "cloudflared-linux-arm64" grabbed straight off GitHub is a normal Linux
#    build and is not guaranteed to satisfy those -- which is exactly what
#    produces errors like "has unexpected e_type: 2" (Android's exec layer
#    rejecting the binary's ELF format on some devices, even though the same
#    file runs fine on a regular Linux box).
if [ -z "$CLOUDFLARED" ] && [ -n "${PREFIX:-}" ] && command -v pkg >/dev/null 2>&1; then
    echo "Checking for a Termux-native cloudflared package..."
    # Termux doesn't reliably provide /tmp, so the log stays in the project
    # directory alongside the other run.sh/tunnel.sh logs.
    if pkg install -y cloudflared >.cloudflared-pkg.log 2>&1; then
        command -v cloudflared >/dev/null 2>&1 && CLOUDFLARED="$(command -v cloudflared)"
    fi
fi

# 3. Fall back to the GitHub release binary. Installed to $PREFIX/bin (the
#    directory Termux itself installs executables into) rather than a
#    project-local .bin/ folder when running under Termux -- termux-exec's
#    exec wrapper is documented to be more reliable for binaries that live
#    there than for ones run from an arbitrary path under $HOME.
if [ -z "$CLOUDFLARED" ]; then
    if [ -n "${PREFIX:-}" ] && [ -d "${PREFIX}/bin" ]; then
        CLOUDFLARED="${PREFIX}/bin/cloudflared"
    else
        CLOUDFLARED="$PWD/.bin/cloudflared"
        mkdir -p .bin
    fi

    if [ ! -x "$CLOUDFLARED" ]; then
        echo "Downloading cloudflared..."
        case "$(uname -m)" in
            aarch64|arm64) CF_ARCH="arm64" ;;
            armv7l|armv8l) CF_ARCH="arm" ;;
            x86_64)        CF_ARCH="amd64" ;;
            *) echo "Unsupported architecture for cloudflared: $(uname -m)" >&2; exit 1 ;;
        esac
        curl -fsSL -o "$CLOUDFLARED" \
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}"
        chmod +x "$CLOUDFLARED"
    fi
fi

# Fail loudly and specifically here, rather than letting a cryptic exec
# error surface for the first time in the middle of the tunnel's own output.
if ! "$CLOUDFLARED" --version >/dev/null 2>&1; then
    echo
    echo "cloudflared won't run on this device ($CLOUDFLARED)." >&2
    echo "This is Android/Termux rejecting the binary's format, not a network" >&2
    echo "problem. Things worth trying, in order:" >&2
    echo "  1. pkg install cloudflared   (a Termux-built package, if one exists)" >&2
    echo "  2. termux-exec: pkg install termux-exec, then restart Termux" >&2
    echo "  3. file \"$CLOUDFLARED\"   -- share the output if you ask for help" >&2
    exit 1
fi

echo "Applying migrations..."
python manage.py migrate --noinput

# Public traffic really is HTTPS -- Cloudflare's edge terminates TLS and
# forwards X-Forwarded-Proto: https to us -- so the HTTPS-only settings
# (secure cookies, HSTS, the SSL redirect) are correct and necessary here.
export HTTPS_ENABLED=True

# The public hostname is only assigned once cloudflared connects, and it's a
# *different* one every run, so there's no exact value to put in ALLOWED_HOSTS
# ahead of time. Django supports domain wildcards for exactly this: a leading
# "." matches any subdomain, and "https://*.host" does the same for CSRF
# origins. This still only accepts trycloudflare.com hosts -- nothing wider.
LAN_IP="$(python - <<'PY' 2>/dev/null
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80)); print(s.getsockname()[0])
except OSError:
    pass
finally:
    s.close()
PY
)"
export ALLOWED_HOSTS=".trycloudflare.com,localhost,127.0.0.1${LAN_IP:+,$LAN_IP}"
export CSRF_TRUSTED_ORIGINS="https://*.trycloudflare.com"

echo "Collecting static files..."
python manage.py collectstatic --noinput >/dev/null

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# --- start gunicorn (daemonised) and wait for it to actually answer ----
echo "Starting HireHorizon..."
rm -f .gunicorn.pid
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2 --daemon \
    --pid .gunicorn.pid --error-logfile .gunicorn.log --access-logfile /dev/null

for _ in $(seq 20); do
    curl -sf -o /dev/null "http://127.0.0.1:${PORT}/" 2>/dev/null && break
    sleep 0.5
done

cleanup() {
    echo
    echo "Stopping..."
    if [ -f .gunicorn.pid ]; then
        kill "$(cat .gunicorn.pid)" 2>/dev/null || true
        rm -f .gunicorn.pid
    fi
}
trap cleanup EXIT INT TERM

echo "Connecting the tunnel..."
echo

# Stream cloudflared's output live, and print a clear banner the moment the
# public URL appears -- it's buried in cloudflared's own log lines otherwise.
"$CLOUDFLARED" tunnel --url "http://127.0.0.1:${PORT}" 2>&1 | while IFS= read -r line; do
    echo "$line"
    url=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' || true)
    if [ -n "$url" ]; then
        echo
        echo "=============================================================="
        echo "  HireHorizon is public at:"
        echo "  $url"
        echo
        echo "  This URL works until you stop this script (Ctrl+C), and will"
        echo "  be different the next time you run it."
        echo "=============================================================="
        echo
    fi
done
