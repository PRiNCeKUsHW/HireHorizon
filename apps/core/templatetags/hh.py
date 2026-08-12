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


@register.inclusion_tag("partials/avatar.html")
def avatar(user, size="md"):
    """CSS avatar built from the user's initials. No uploads anywhere."""
    return {"user": user, "size": size}
