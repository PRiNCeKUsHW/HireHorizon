import zlib

from django import template
from django.urls import reverse
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

from apps.core.utils import MENTION_RE

register = template.Library()


@register.filter
def rich_text(value):
    """Render user-written text: escape it, link @mentions, keep line breaks.

    Order matters. The text is escaped *first*, so nothing a user types can
    become markup; only the anchors this function builds are trusted. Mention
    names match [A-Za-z0-9_] only, so they are safe to interpolate into href.
    """
    if not value:
        return ""

    escaped = escape(value)

    def link(match):
        username = match.group(1)
        url = reverse("accounts:profile", kwargs={"username": username})
        return f'<a class="mention" href="{url}">@{username}</a>'

    return mark_safe(linebreaks(MENTION_RE.sub(link, escaped)))


@register.filter
def compact(number):
    """1200 -> 1.2K, for counts on post cards."""
    try:
        number = int(number)
    except (TypeError, ValueError):
        return "0"
    if number < 1000:
        return str(number)
    if number < 1_000_000:
        trimmed = round(number / 1000, 1)
        return f"{trimmed:g}K"
    return f"{round(number / 1_000_000, 1):g}M"


AVATAR_HUE_COUNT = 4


@register.inclusion_tag("partials/avatar.html")
def avatar(user, size="md"):
    """CSS avatar built from the user's initials. No uploads anywhere.

    The gradient variant is picked from a small fixed set via a stable hash
    of the username. This uses crc32, not Python's built-in hash() — hash()
    is salted per process via PYTHONHASHSEED, so under multiple gunicorn
    workers the same user would render a different avatar colour depending
    on which worker answered the request.
    """
    hue = zlib.crc32(user.username.encode("utf-8")) % AVATAR_HUE_COUNT
    return {"user": user, "size": size, "hue": hue}


# Stroke-based icon set in the Lucide visual language: 24x24 grid, 2px
# stroke, round caps/joins. Self-hosted as inline SVG (no icon font, no CDN)
# so the app makes no extra request and stays offline-friendly. Every call
# site uses the same handful of names, so a typo fails loudly with KeyError
# rather than silently rendering nothing.
ICONS = {
    "home": '<path d="M3 9.5 12 3l9 6.5"/><path d="M5 10v10a1 1 0 0 0 1 1h4v-7h4v7h4a1 1 0 0 0 1-1V10"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "bookmark": '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>',
    "message-circle": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "chevron-left": '<polyline points="15 18 9 12 15 6"/>',
    "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "arrow-left": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "map-pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "sparkle": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.287 1.288L3 12l5.8 1.9a2 2 0 0 1 1.288 1.287L12 21l1.9-5.8a2 2 0 0 1 1.287-1.288L21 12l-5.8-1.9a2 2 0 0 1-1.288-1.287Z"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
}


@register.simple_tag
def icon(name, size=20, css_class=""):
    """Inline SVG icon, self-hosted — see ICONS above.

    Returned as markup, not a filename: no icon font, no per-icon HTTP
    request, and every icon inherits `currentColor` for free.
    """
    body = ICONS.get(name)
    if body is None:
        raise KeyError(f"Unknown icon '{name}'. Add it to ICONS in hh.py.")
    classes = f"icon {css_class}".strip()
    return mark_safe(
        f'<svg class="{classes}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


@register.filter
def a11y_field(field):
    """Render a form widget wired to its own help text and errors.

    A plain ``{{ field }}`` emits the widget alone, so the error rendered
    beside it is visible but not announced as part of the field — a screen
    reader reaches the input, says nothing about the problem, and only meets
    the message later as loose text. The ids referenced here are emitted by
    partials/field.html.
    """
    described_by = []
    if field.help_text:
        described_by.append(f"{field.auto_id}_help")
    if field.errors:
        described_by.append(f"{field.auto_id}_error")

    attrs = {}
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if field.errors:
        attrs["aria-invalid"] = "true"
    return field.as_widget(attrs=attrs)
