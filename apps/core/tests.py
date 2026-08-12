from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.blog.models import Post
from apps.core.models import ContactMessage
from apps.notifications.models import Notification

User = get_user_model()


class ContactTests(TestCase):
    def test_submission_saved_to_database(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "name": "Anuj",
                "email": "anuj@example.com",
                "subject": "Hello",
                "message": "This is a long enough message.",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = ContactMessage.objects.get()
        self.assertEqual(entry.subject, "Hello")
        self.assertEqual(entry.status, ContactMessage.Status.NEW)

    def test_no_email_is_sent(self):
        self.client.post(
            reverse("core:contact"),
            {
                "name": "Anuj",
                "email": "anuj@example.com",
                "subject": "Hello",
                "message": "This is a long enough message.",
            },
        )
        # SMTP is gone: nothing may be queued or sent.
        self.assertEqual(len(mail.outbox), 0)

    def test_short_message_rejected(self):
        self.client.post(
            reverse("core:contact"),
            {"name": "A", "email": "a@example.com", "subject": "s", "message": "hi"},
        )
        self.assertEqual(ContactMessage.objects.count(), 0)


class PageTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.post = Post.objects.create(
            author=self.alice, title="Findable Title", content="searchable body text"
        )

    def test_landing_page_for_anonymous(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Where Ideas Find Their Horizon")

    def test_feed_for_authenticated_user(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Findable Title")

    def test_explore_is_public(self):
        response = self.client.get(reverse("core:explore"))
        self.assertEqual(response.status_code, 200)

    def test_search_finds_posts(self):
        response = self.client.get(reverse("core:search"), {"q": "Findable"})
        self.assertContains(response, "Findable Title")

    def test_search_finds_people(self):
        response = self.client.get(
            reverse("core:search"), {"q": "alice", "tab": "people"}
        )
        self.assertContains(response, "@alice")

    def test_search_with_no_results(self):
        response = self.client.get(reverse("core:search"), {"q": "zzzznotfound"})
        self.assertContains(response, "No posts found")

    def test_404_page(self):
        response = self.client.get("/definitely-not-a-real-page/")
        self.assertEqual(response.status_code, 404)


class NotificationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(author=self.alice, title="Notify", content="x")

    def test_like_notifies_author(self):
        self.client.force_login(self.bob)
        self.client.post(reverse("blog:toggle_like", args=[self.post.slug]))
        note = Notification.objects.get()
        self.assertEqual(note.recipient, self.alice)
        self.assertEqual(note.notification_type, Notification.Type.LIKE)

    def test_comment_notifies_author(self):
        self.client.force_login(self.bob)
        self.client.post(
            reverse("blog:add_comment", args=[self.post.slug]), {"body": "great read"}
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, notification_type=Notification.Type.COMMENT
            ).exists()
        )

    def test_follow_notifies_target(self):
        self.client.force_login(self.bob)
        self.client.post(reverse("accounts:toggle_follow", args=["alice"]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, notification_type=Notification.Type.FOLLOW
            ).exists()
        )

    def test_mention_creates_notification(self):
        self.client.force_login(self.bob)
        self.client.post(
            reverse("blog:post_create"),
            {"title": "Hi", "content": "thanks @alice", "status": "published"},
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, notification_type=Notification.Type.MENTION
            ).exists()
        )

    def test_no_self_notification(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("blog:toggle_like", args=[self.post.slug]))
        self.assertEqual(Notification.objects.count(), 0)

    def test_opening_list_marks_read(self):
        Notification.push(
            recipient=self.alice,
            actor=self.bob,
            notification_type=Notification.Type.FOLLOW,
        )
        self.client.force_login(self.alice)
        self.client.get(reverse("notifications:list"))
        self.assertEqual(
            Notification.objects.filter(recipient=self.alice, is_read=False).count(), 0
        )
