from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, F
from django.urls import reverse


class User(AbstractUser):
    """Site user.

    Deliberately has no avatar/image field: profile pictures are rendered from
    the user's initials in CSS, so there is no upload surface anywhere.
    """

    display_name = models.CharField(max_length=50, blank=True)
    bio = models.TextField(max_length=280, blank=True)
    location = models.CharField(max_length=60, blank=True)
    website = models.URLField(blank=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.username

    def get_absolute_url(self):
        return reverse("accounts:profile", kwargs={"username": self.username})

    @property
    def name(self):
        """Display name when set, otherwise the username."""
        return self.display_name.strip() or self.username

    @property
    def initials(self):
        """Up to two letters used by the CSS avatar."""
        source = self.display_name.strip() or self.username
        parts = [p for p in source.replace("_", " ").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    def is_following(self, other):
        if not other or not self.is_authenticated:
            return False
        return Follow.objects.filter(follower=self, following=other).exists()


class Follow(models.Model):
    """A directed follow edge. follower -> following."""

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_set",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers_set",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One edge per pair, enforced by the database rather than by views.
            models.UniqueConstraint(
                fields=["follower", "following"], name="uniq_follow_pair"
            ),
            # Following yourself is meaningless; block it at the database too.
            models.CheckConstraint(
                condition=~Q(follower=F("following")), name="no_self_follow"
            ),
        ]
        indexes = [
            models.Index(fields=["following", "-created_at"]),
            models.Index(fields=["follower", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower} follows {self.following}"
