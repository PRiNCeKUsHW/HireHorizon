from django.db import models


class ContactMessage(models.Model):
    """A contact-form submission.

    Stored in the database and read in the admin. The site sends no email at
    all, so nothing here depends on SMTP being configured.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        READ = "read", "Read"
        RESOLVED = "resolved", "Resolved"

    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=4000)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.subject} — {self.name}"

    @property
    def is_read(self):
        return self.status != self.Status.NEW
