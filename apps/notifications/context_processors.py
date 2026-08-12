from .models import Notification


def notification_badge(request):
    """Unread counts for the navigation badge.

    Cheap enough to run on every page: one indexed COUNT for signed-in users,
    and nothing at all for anonymous ones.
    """
    if not request.user.is_authenticated:
        return {"unread_notifications": 0}
    return {
        "unread_notifications": Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
    }
