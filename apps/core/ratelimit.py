"""A small, dependency-free per-IP rate limiter for POST endpoints.

Used on login, registration and the contact form -- the surfaces a public,
unauthenticated URL exposes to credential stuffing and spam. Built by hand
instead of pulling in a package because the whole thing is ~20 lines and this
project stays intentionally light on dependencies (it has to `pip install`
cleanly on a phone).
"""

import time
from functools import wraps

from django.core.cache import cache
from django.shortcuts import render


def client_ip(request):
    """Best-effort client IP, resistant to spoofing when behind the tunnel.

    CF-Connecting-IP is set by Cloudflare's edge and can't be forged by the
    client when a request genuinely arrives through Cloudflare -- the edge
    overwrites anything the client tried to send in that header. Direct LAN
    access (no proxy in front) has no such guarantee, so REMOTE_ADDR is the
    honest fallback there; a LAN client could spoof X-Forwarded-For, so that
    header is deliberately not trusted for this.
    """
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get(
        "REMOTE_ADDR", "unknown"
    )


def rate_limit(scope, limit, window_seconds):
    """Allow at most `limit` POSTs per `window_seconds`, per client IP.

    GET requests always pass through untouched -- viewing a login, register
    or contact page should never be throttled, only submitting one. Requests
    over the limit render a 429 without reaching the view.

    This is a fixed window: the count resets `window_seconds` after the
    *first* request in the window, not after each request. It's implemented
    by hand rather than via cache.incr(), because Django's default incr()
    re-applies the cache's default TIMEOUT on every call instead of
    preserving the window's own expiry (BaseCache.incr() calls self.set()
    with no timeout argument) -- which would silently replace every
    caller's window with the cache's global default. Storing the window's
    start time inside the cached value sidesteps that entirely.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view_func(request, *args, **kwargs)

            key = f"ratelimit:{scope}:{client_ip(request)}"
            now = time.time()
            window_start, count = cache.get(key, (now, 0))

            if now - window_start >= window_seconds:
                window_start, count = now, 0

            if count >= limit:
                return render(request, "errors/429.html", status=429)

            cache.set(key, (window_start, count + 1), window_seconds)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
