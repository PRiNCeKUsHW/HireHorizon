"""Import users, posts and comments from the old Flask/SQLAlchemy database.

The previous version of HireHorizon was a Flask app storing data in
instance/posts.db (or a Postgres database with the same three tables). This
command copies that content into the Django models.

Passwords cannot be carried over: the old app used Werkzeug's pbkdf2 format,
which Django's hashers do not understand. Imported accounts are created with an
unusable password, so the owner keeps their username and content but an admin
must set a new password with `manage.py changepassword <username>`.
"""

import sqlite3
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.blog.models import Comment, Post

User = get_user_model()


class Command(BaseCommand):
    help = "Import data from the legacy Flask SQLite database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="instance/posts.db",
            help="Path to the legacy SQLite file (default: instance/posts.db).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be imported without writing anything.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"No legacy database at {path}")

        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"users", "blog_posts", "comments"}
        if not required.issubset(tables):
            raise CommandError(
                f"{path} does not look like a legacy HireHorizon database "
                f"(missing {required - tables})."
            )

        legacy_users = list(connection.execute("SELECT * FROM users"))
        legacy_posts = list(connection.execute("SELECT * FROM blog_posts"))
        legacy_comments = list(connection.execute("SELECT * FROM comments"))

        self.stdout.write(
            f"Found {len(legacy_users)} user(s), {len(legacy_posts)} post(s), "
            f"{len(legacy_comments)} comment(s)."
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing written."))
            return

        with transaction.atomic():
            user_map = self._import_users(legacy_users)
            post_map = self._import_posts(legacy_posts, user_map)
            self._import_comments(legacy_comments, user_map, post_map)

        self.stdout.write(
            self.style.SUCCESS(
                "Import complete. Imported accounts have no usable password — "
                "set one with: python manage.py changepassword <username>"
            )
        )

    def _username_for(self, row):
        """Derive a username from the legacy name, falling back to the email."""
        raw = (row["name"] or "").strip() or (row["email"] or "").split("@")[0]
        base = "".join(c for c in raw if c.isalnum() or c in "._-") or "user"
        username = base[:30]
        suffix = 2
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base[:26]}{suffix}"
            suffix += 1
        return username

    def _import_users(self, rows):
        mapping = {}
        for row in rows:
            existing = User.objects.filter(email__iexact=row["email"]).first()
            if existing:
                mapping[row["id"]] = existing
                self.stdout.write(f"  user {row['email']}: already present, reused")
                continue

            user = User.objects.create(
                username=self._username_for(row),
                email=(row["email"] or "").lower(),
                display_name=(row["name"] or "").strip()[:50],
            )
            # Werkzeug hashes are not portable to Django; force a reset.
            user.set_unusable_password()
            user.save(update_fields=["password"])
            mapping[row["id"]] = user
            self.stdout.write(f"  user {row['email']} -> @{user.username}")
        return mapping

    def _import_posts(self, rows, user_map):
        mapping = {}
        for row in rows:
            author = user_map.get(row["author_id"])
            if author is None:
                self.stdout.write(
                    self.style.WARNING(f"  post {row['id']}: unknown author, skipped")
                )
                continue

            # The legacy schema kept the subtitle and an image URL. The subtitle
            # is folded into the body; the image URL is dropped, since
            # HireHorizon is text-only now.
            body = row["body"] or ""
            subtitle = (row["subtitle"] or "").strip()
            content = f"{subtitle}\n\n{body}" if subtitle else body

            post = Post.objects.create(
                author=author,
                title=(row["title"] or "Untitled")[:200],
                content=content,
                status=Post.Status.PUBLISHED,
                created_at=timezone.now(),
            )
            mapping[row["id"]] = post
            self.stdout.write(f"  post {row['id']} -> {post.slug}")
        return mapping

    def _import_comments(self, rows, user_map, post_map):
        for row in rows:
            author = user_map.get(row["author_id"])
            post = post_map.get(row["post_id"])
            if author is None or post is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  comment {row['id']}: missing author or post, skipped"
                    )
                )
                continue
            Comment.objects.create(post=post, author=author, body=row["text"] or "")
        self.stdout.write(f"  imported {len(rows)} comment(s)")
