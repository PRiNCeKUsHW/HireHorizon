from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils import timezone


class Conversation(models.Model):
    """A private thread between two or more users. Text only."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation #{self.pk}"

    def other_participant(self, user):
        """The first participant who isn't `user` (direct messages have one)."""
        for participant in self.participants.all():
            if participant.user_id != user.pk:
                return participant.user
        return None

    def has_participant(self, user):
        if not user.is_authenticated:
            return False
        return self.participants.filter(user=user).exists()

    @classmethod
    def between(cls, user_a, user_b):
        """Find the existing direct conversation between two users, if any.

        Matched via two id subqueries rather than chained joins on the same
        relation: joining twice and counting the rows overcounts participants
        and makes the `n=2` test never match.
        """
        a_ids = ConversationParticipant.objects.filter(user=user_a).values(
            "conversation_id"
        )
        b_ids = ConversationParticipant.objects.filter(user=user_b).values(
            "conversation_id"
        )
        return (
            cls.objects.filter(pk__in=a_ids)
            .filter(pk__in=b_ids)
            .annotate(participant_total=Count("participants", distinct=True))
            .filter(participant_total=2)
            .first()
        )

    @classmethod
    def start(cls, user_a, user_b):
        """Get or create the direct conversation between two users."""
        existing = cls.between(user_a, user_b)
        if existing:
            return existing
        conversation = cls.objects.create()
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, user=user_a),
                ConversationParticipant(conversation=conversation, user=user_b),
            ]
        )
        return conversation


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="uniq_conversation_participant"
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.conversation}"

    def mark_read(self):
        self.last_read_at = timezone.now()
        self.save(update_fields=["last_read_at"])


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"
