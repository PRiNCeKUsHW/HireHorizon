from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    """Something another user did that concerns you."""

    class Type(models.TextChoices):
        FOLLOW = "follow", "started following you"
        LIKE = "like", "liked your post"
        COMMENT = "comment", "commented on your post"
        REPLY = "reply", "replied to your comment"
        MENTION = "mention", "mentioned you"
        REPOST = "repost", "reposted your post"
        MESSAGE = "message", "sent you a message"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    notification_type = models.CharField(max_length=20, choices=Type.choices)

    # Generic link to whatever the notification is about (a post, a comment,
    # a conversation), so new notification kinds don't need new columns.
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.get_notification_type_display()} -> {self.recipient}"

    @property
    def verb(self):
        return self.get_notification_type_display()

    @property
    def target_url(self):
        """Where clicking the notification should land."""
        obj = self.related_object
        if obj is None:
            return self.actor.get_absolute_url()
        get_url = getattr(obj, "get_absolute_url", None)
        if callable(get_url):
            return get_url()
        return self.actor.get_absolute_url()

    @classmethod
    def push(cls, *, recipient, actor, notification_type, related_object=None):
        """Create a notification, skipping self-notifications and duplicates.

        Acting on your own content should never notify you, and repeatedly
        liking/unliking a post should not stack identical unread rows.
        """
        if recipient is None or recipient.pk == actor.pk:
            return None

        fields = {
            "recipient": recipient,
            "actor": actor,
            "notification_type": notification_type,
        }
        if related_object is not None:
            fields["content_type"] = ContentType.objects.get_for_model(related_object)
            fields["object_id"] = related_object.pk

        # Collapse repeats that are still unread.
        existing = cls.objects.filter(is_read=False, **fields).first()
        if existing:
            return existing
        return cls.objects.create(**fields)
