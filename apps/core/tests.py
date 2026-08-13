from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.blog.models import Post
from apps.core.models import ContactMessage
from apps.core.ratelimit import client_ip, rate_limit
from apps.notifications.models import Notification

User = get_user_model()


def _valid_contact_data(**overrides):
    data = {
        "name": "Anuj",
        "email": "anuj@example.com",
        "subject": "Hello",
        "message": "This is a long enough message.",
    }
    data.update(overrides)
    return data


class ContactTests(TestCase):
    def setUp(self):
        # See AuthTests.setUp: the rate-limit cache persists across the
        # whole test run under the test client's fixed REMOTE_ADDR.
        cache.clear()

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


class ContactRateLimitTests(TestCase):
    """Contact is limited to 5 POSTs / hour per IP (core/views.py)."""

    def setUp(self):
        cache.clear()

    def test_get_is_never_throttled(self):
        for _ in range(8):
            self.assertEqual(self.client.get(reverse("core:contact")).status_code, 200)

    def test_blocks_after_limit_then_recovers_for_a_different_ip(self):
        for _ in range(5):
            response = self.client.post(reverse("core:contact"), _valid_contact_data())
            self.assertEqual(response.status_code, 302)

        blocked = self.client.post(reverse("core:contact"), _valid_contact_data())
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(ContactMessage.objects.count(), 5)

        response = self.client.post(
            reverse("core:contact"), _valid_contact_data(), REMOTE_ADDR="203.0.113.9"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 6)


class RateLimitDecoratorTests(TestCase):
    """Unit tests of apps/core/ratelimit.py against a throwaway view, so
    window-reset behaviour can be tested in ~1 second instead of an hour.
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _request(self, method, **extra):
        """A request shaped like AuthenticationMiddleware would leave it.

        RequestFactory doesn't run the middleware stack, so request.user
        isn't set -- but the blocked path renders base.html, whose
        notification_badge context processor reads it. Anonymous is correct
        here anyway: these are the same unauthenticated form endpoints the
        real rate limits protect.
        """
        request = getattr(self.factory, method)("/", **extra)
        request.user = AnonymousUser()
        return request

    def _throttled_view(self, limit=3, window_seconds=1):
        @rate_limit("unit-test", limit=limit, window_seconds=window_seconds)
        def view(request):
            from django.http import HttpResponse

            return HttpResponse("ok")

        return view

    def test_client_ip_prefers_cf_connecting_ip(self):
        request = self._request(
            "get", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.5"
        )
        self.assertEqual(client_ip(request), "198.51.100.5")

    def test_client_ip_falls_back_to_remote_addr(self):
        request = self._request("get", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(client_ip(request), "10.0.0.1")

    def test_allows_up_to_the_limit_then_blocks(self):
        view = self._throttled_view(limit=3, window_seconds=60)
        for _ in range(3):
            request = self._request("post", REMOTE_ADDR="10.0.0.1")
            self.assertEqual(view(request).status_code, 200)

        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 429)

    def test_get_requests_bypass_the_limit_entirely(self):
        view = self._throttled_view(limit=1, window_seconds=60)
        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 200)

        for _ in range(5):
            request = self._request("get", REMOTE_ADDR="10.0.0.1")
            self.assertEqual(view(request).status_code, 200)

    def test_window_resets_after_it_elapses(self):
        import time

        view = self._throttled_view(limit=2, window_seconds=1)
        for _ in range(2):
            request = self._request("post", REMOTE_ADDR="10.0.0.1")
            self.assertEqual(view(request).status_code, 200)

        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 429)

        time.sleep(1.2)

        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 200)

    def test_flooding_while_blocked_does_not_extend_the_block(self):
        """A burst of requests after the limit is hit must not push the
        window's reset time further out -- otherwise an attacker could keep
        someone locked out indefinitely just by continuing to hammer it.

        The window (3s) comfortably outlasts the flood (5 x 0.3s = 1.5s), so
        every flooded request lands while still genuinely inside the
        original window -- this is testing that flooding doesn't extend it,
        not incidentally waiting the window out.
        """
        import time

        view = self._throttled_view(limit=1, window_seconds=3)
        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 200)

        for _ in range(5):
            request = self._request("post", REMOTE_ADDR="10.0.0.1")
            self.assertEqual(view(request).status_code, 429)
            time.sleep(0.3)

        # The flood is over; the *original* 3s window should still recover
        # on schedule rather than having been pushed out by it.
        time.sleep(2)
        request = self._request("post", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(view(request).status_code, 200)
