import re

from django.contrib.auth import get_user_model

# @username — 1-30 chars, letters/digits/underscore, matching Django's default
# username charset closely enough for mention detection.
MENTION_RE = re.compile(r"@([A-Za-z0-9_]{1,30})")


def extract_mentions(text):
    """Return the User objects mentioned as @username in `text`.

    Looks the names up in one query and returns real users only, so a typo
    silently does nothing instead of creating a dangling notification.
    """
    if not text:
        return []
    names = {m.lower() for m in MENTION_RE.findall(text)}
    if not names:
        return []
    User = get_user_model()
    return list(User.objects.filter(username__in=names))


def notify_mentions(*, text, actor, related_object):
    """Create mention notifications for everyone named in `text`."""
    from apps.notifications.models import Notification

    for user in extract_mentions(text):
        Notification.push(
            recipient=user,
            actor=actor,
            notification_type=Notification.Type.MENTION,
            related_object=related_object,
        )
