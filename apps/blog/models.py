from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Post.Status.PUBLISHED)

    def with_counts(self):
        """Annotate the counts every post card needs, in one query."""
        return self.annotate(
            like_count=models.Count("likes", distinct=True),
            comment_count=models.Count("comments", distinct=True),
            repost_count=models.Count("reposts", distinct=True),
            view_count=models.Count("views", distinct=True),
        )

    def for_feed(self):
        """Everything a post card renders, without N+1 queries."""
        return self.select_related("author").with_counts()


class Post(models.Model):
    """A text post. Longer than a tweet, shorter than a book."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    content = models.TextField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PUBLISHED
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def _build_unique_slug(self):
        base = slugify(self.title)[:200] or "post"
        slug = base
        suffix = 2
        while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def excerpt(self):
        text = self.content.strip()
        return text if len(text) <= 240 else text[:240].rsplit(" ", 1)[0] + "…"

    @property
    def reading_time(self):
        """Rounded minutes at ~200 words per minute, minimum 1."""
        return max(1, round(len(self.content.split()) / 200))


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "created_at"])]

    def __str__(self):
        return f"{self.author} on {self.post}"

    @property
    def is_edited(self):
        return (self.updated_at - self.created_at).total_seconds() > 1


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="uniq_like_user_post")
        ]
        indexes = [models.Index(fields=["user", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} likes {self.post}"


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"], name="uniq_bookmark_user_post"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bookmarked {self.post}"


class Repost(models.Model):
    """A plain re-share. Text only, no quote body."""

    original_post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="reposts"
    )
    reposted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reposts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["original_post", "reposted_by"], name="uniq_repost_user_post"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reposted_by} reposted {self.original_post}"


class PostView(models.Model):
    """One row per (post, viewer). Never more.

    The uniqueness is enforced by the database, so refreshing the page, opening
    it in another tab or coming back tomorrow cannot inflate the count. Signed-in
    viewers are keyed on the user; anonymous viewers on the session key, which
    keeps anonymous counts approximately honest without pretending an IP is an
    identity.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="post_views",
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One authenticated user = one view per post.
            models.UniqueConstraint(
                fields=["post", "user"],
                condition=Q(user__isnull=False),
                name="uniq_view_post_user",
            ),
            # One anonymous session = one view per post.
            models.UniqueConstraint(
                fields=["post", "session_key"],
                condition=Q(user__isnull=True),
                name="uniq_view_post_session",
            ),
        ]
        indexes = [models.Index(fields=["post", "-created_at"])]

    def __str__(self):
        return f"view of {self.post} by {self.user or self.session_key or 'anon'}"
