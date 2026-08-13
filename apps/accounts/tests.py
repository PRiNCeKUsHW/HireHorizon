from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Follow

User = get_user_model()


class AuthTests(TestCase):
    def setUp(self):
        # The test client reuses the same REMOTE_ADDR for every test, and the
        # rate-limit cache persists across the whole test run, so a stale
        # counter left by an earlier test could make an unrelated test start
        # returning 429 here.
        cache.clear()

    def test_registration_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "display_name": "New Bie",
                "password1": "a-strong-pass-99",
                "password2": "a-strong-pass-99",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newbie")
        self.assertEqual(user.display_name, "New Bie")
        self.assertIn("_auth_user_id", self.client.session)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("first", email="dupe@example.com", password="pw-123456789")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "second",
                "email": "dupe@example.com",
                "password1": "a-strong-pass-99",
                "password2": "a-strong-pass-99",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="second").exists())

    def test_login_and_logout(self):
        User.objects.create_user("alice", password="pw-alice-123")
        response = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "pw-alice-123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_bad_password(self):
        User.objects.create_user("alice", password="pw-alice-123")
        response = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_superuser_can_be_created(self):
        admin = User.objects.create_superuser(
            "root", email="root@example.com", password="pw-root-12345"
        )
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/admin/").status_code, 200)


class ProfileTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", password="pw-alice-123", display_name="Alice A"
        )

    def test_public_profile_visible_to_anonymous(self):
        response = self.client.get(reverse("accounts:profile", args=["alice"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@alice")

    def test_profile_url_uses_at_form(self):
        self.assertEqual(self.alice.get_absolute_url(), "/@alice/")

    def test_edit_profile(self):
        self.client.force_login(self.alice)
        self.client.post(
            reverse("accounts:edit_profile"),
            {"display_name": "Alice Updated", "bio": "hello", "location": "", "website": ""},
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.display_name, "Alice Updated")

    def test_initials_fall_back_to_username(self):
        bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.assertEqual(bob.initials, "BO")
        self.assertEqual(self.alice.initials, "AA")


class FollowTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.url = reverse("accounts:toggle_follow", args=["bob"])

    def test_follow_then_unfollow(self):
        self.client.force_login(self.alice)
        self.client.post(self.url)
        self.assertTrue(Follow.objects.filter(follower=self.alice, following=self.bob).exists())
        self.client.post(self.url)
        self.assertFalse(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_cannot_follow_self(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("accounts:toggle_follow", args=["alice"]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Follow.objects.count(), 0)

    def test_self_follow_blocked_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(follower=self.alice, following=self.alice)

    def test_duplicate_follow_blocked_by_database(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(follower=self.alice, following=self.bob)

    def test_follow_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Follow.objects.count(), 0)

    def test_follower_lists_render(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        response = self.client.get(reverse("accounts:followers", args=["bob"]))
        self.assertContains(response, "@alice")
        response = self.client.get(reverse("accounts:following", args=["alice"]))
        self.assertContains(response, "@bob")


class LoginRateLimitTests(TestCase):
    """Login is limited to 10 POSTs / 5 minutes per IP (accounts/views.py)."""

    def setUp(self):
        cache.clear()
        User.objects.create_user("alice", password="pw-alice-123")

    def test_get_is_never_throttled(self):
        for _ in range(15):
            self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)

    def test_blocks_after_limit_then_recovers_for_a_different_ip(self):
        for _ in range(10):
            response = self.client.post(
                reverse("accounts:login"), {"username": "alice", "password": "wrong"}
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "wrong"}
        )
        self.assertEqual(blocked.status_code, 429)

        # A legitimate login from the same (blocked) IP is refused too --
        # the limit is on attempts, not on failures specifically.
        still_blocked = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "pw-alice-123"}
        )
        self.assertEqual(still_blocked.status_code, 429)

        # A different client IP has its own, untouched quota.
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "alice", "password": "pw-alice-123"},
            REMOTE_ADDR="203.0.113.9",
        )
        self.assertEqual(response.status_code, 302)

    def test_cf_connecting_ip_is_preferred_over_remote_addr(self):
        # Same REMOTE_ADDR throughout, but different CF-Connecting-IP values
        # -- behind the tunnel, that's the header that identifies the real
        # visitor, and each value must get its own quota.
        for _ in range(10):
            response = self.client.post(
                reverse("accounts:login"),
                {"username": "alice", "password": "wrong"},
                HTTP_CF_CONNECTING_IP="198.51.100.1",
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            reverse("accounts:login"),
            {"username": "alice", "password": "wrong"},
            HTTP_CF_CONNECTING_IP="198.51.100.1",
        )
        self.assertEqual(blocked.status_code, 429)

        # Different CF-Connecting-IP, same REMOTE_ADDR: untouched quota.
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "alice", "password": "wrong"},
            HTTP_CF_CONNECTING_IP="198.51.100.2",
        )
        self.assertEqual(response.status_code, 200)


class RegisterRateLimitTests(TestCase):
    """Register is limited to 5 POSTs / hour per IP (accounts/views.py)."""

    def setUp(self):
        cache.clear()

    def test_get_is_never_throttled(self):
        for _ in range(8):
            self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 200)

    def test_blocks_after_limit(self):
        for i in range(5):
            response = self.client.post(
                reverse("accounts:register"),
                {
                    "username": f"user{i}",
                    "email": f"user{i}@example.com",
                    "password1": "a-strong-pass-99",
                    "password2": "a-strong-pass-99",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.client.post(reverse("accounts:logout"))

        blocked = self.client.post(
            reverse("accounts:register"),
            {
                "username": "user5",
                "email": "user5@example.com",
                "password1": "a-strong-pass-99",
                "password2": "a-strong-pass-99",
            },
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertFalse(User.objects.filter(username="user5").exists())
