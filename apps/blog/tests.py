from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.blog.models import Bookmark, Comment, Like, Post, PostView, Repost

User = get_user_model()


class PostTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(
            author=self.alice, title="My Journey Learning Django", content="It began."
        )

    def test_slug_is_generated_and_unique(self):
        second = Post.objects.create(
            author=self.alice, title="My Journey Learning Django", content="Again."
        )
        self.assertEqual(self.post.slug, "my-journey-learning-django")
        self.assertNotEqual(second.slug, self.post.slug)

    def test_create_post(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("blog:post_create"),
            {"title": "Second post", "content": "Body text", "status": "published"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.filter(title="Second post").exists())

    def test_create_requires_login(self):
        response = self.client.post(
            reverse("blog:post_create"),
            {"title": "Nope", "content": "x", "status": "published"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
        self.assertFalse(Post.objects.filter(title="Nope").exists())

    def test_author_can_edit_own_post(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("blog:post_edit", args=[self.post.slug]),
            {"title": "Edited", "content": "New body", "status": "published"},
        )
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Edited")

    def test_other_user_cannot_edit_post(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("blog:post_edit", args=[self.post.slug]),
            {"title": "Hacked", "content": "x", "status": "published"},
        )
        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "My Journey Learning Django")

    def test_other_user_cannot_delete_post(self):
        self.client.force_login(self.bob)
        response = self.client.post(reverse("blog:post_delete", args=[self.post.slug]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_author_can_delete_own_post(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("blog:post_delete", args=[self.post.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_public_post_visible_to_anonymous(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Journey Learning Django")

    def test_draft_hidden_from_others(self):
        draft = Post.objects.create(
            author=self.alice, title="Secret draft", content="x", status="draft"
        )
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 403)

        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 200)


class ViewCountTests(TestCase):
    """The headline requirement: one authenticated user = one view per post."""

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(
            author=self.alice, title="Counting views", content="x"
        )

    def views(self):
        return PostView.objects.filter(post=self.post).count()

    def test_first_authenticated_visit_counts(self):
        self.client.force_login(self.bob)
        self.client.get(self.post.get_absolute_url())
        self.assertEqual(self.views(), 1)

    def test_refresh_does_not_increment(self):
        self.client.force_login(self.bob)
        for _ in range(5):
            self.client.get(self.post.get_absolute_url())
        self.assertEqual(self.views(), 1)

    def test_reopen_after_logout_does_not_increment(self):
        self.client.force_login(self.bob)
        self.client.get(self.post.get_absolute_url())
        self.client.logout()
        self.client.force_login(self.bob)
        self.client.get(self.post.get_absolute_url())
        self.assertEqual(self.views(), 1)

    def test_different_user_counts_separately(self):
        self.client.force_login(self.bob)
        self.client.get(self.post.get_absolute_url())
        self.client.logout()
        self.client.force_login(self.alice)
        self.client.get(self.post.get_absolute_url())
        self.assertEqual(self.views(), 2)

    def test_duplicate_view_rejected_by_database(self):
        PostView.objects.create(post=self.post, user=self.bob)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PostView.objects.create(post=self.post, user=self.bob)

    def test_anonymous_session_counted_once(self):
        for _ in range(4):
            self.client.get(self.post.get_absolute_url())
        self.assertEqual(self.views(), 1)


class LikeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(author=self.alice, title="Likeable", content="x")
        self.url = reverse("blog:toggle_like", args=[self.post.slug])

    def test_like_then_unlike(self):
        self.client.force_login(self.bob)
        self.client.post(self.url)
        self.assertEqual(Like.objects.filter(post=self.post).count(), 1)
        self.client.post(self.url)
        self.assertEqual(Like.objects.filter(post=self.post).count(), 0)

    def test_duplicate_like_blocked_by_database(self):
        Like.objects.create(user=self.bob, post=self.post)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=self.bob, post=self.post)

    def test_like_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Like.objects.count(), 0)

    def test_get_not_allowed(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class BookmarkRepostTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(author=self.alice, title="Saveable", content="x")

    def test_bookmark_and_remove(self):
        self.client.force_login(self.bob)
        url = reverse("blog:toggle_bookmark", args=[self.post.slug])
        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_duplicate_bookmark_blocked(self):
        Bookmark.objects.create(user=self.bob, post=self.post)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Bookmark.objects.create(user=self.bob, post=self.post)

    def test_duplicate_repost_blocked(self):
        Repost.objects.create(original_post=self.post, reposted_by=self.bob)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Repost.objects.create(original_post=self.post, reposted_by=self.bob)

    def test_bookmarks_page_lists_saved_posts(self):
        self.client.force_login(self.bob)
        Bookmark.objects.create(user=self.bob, post=self.post)
        response = self.client.get(reverse("blog:bookmarks"))
        self.assertContains(response, "Saveable")


class CommentTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.post = Post.objects.create(author=self.alice, title="Discuss", content="x")

    def test_create_comment(self):
        self.client.force_login(self.bob)
        self.client.post(
            reverse("blog:add_comment", args=[self.post.slug]), {"body": "Nice post"}
        )
        self.assertEqual(Comment.objects.count(), 1)

    def test_edit_own_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.bob, body="first")
        self.client.force_login(self.bob)
        self.client.post(reverse("blog:comment_edit", args=[comment.pk]), {"body": "edited"})
        comment.refresh_from_db()
        self.assertEqual(comment.body, "edited")

    def test_cannot_edit_others_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.bob, body="first")
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("blog:comment_edit", args=[comment.pk]), {"body": "hacked"}
        )
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "first")

    def test_cannot_delete_others_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.bob, body="first")
        self.client.force_login(self.alice)
        response = self.client.post(reverse("blog:comment_delete", args=[comment.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_reply_must_belong_to_same_post(self):
        other_post = Post.objects.create(author=self.alice, title="Other", content="x")
        stray = Comment.objects.create(post=other_post, author=self.alice, body="stray")
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("blog:add_comment", args=[self.post.slug]),
            {"body": "reply", "parent": stray.pk},
        )
        self.assertEqual(response.status_code, 404)


class XssTests(TestCase):
    def test_post_content_is_escaped(self):
        alice = User.objects.create_user("alice", password="pw-alice-123")
        post = Post.objects.create(
            author=alice,
            title="Safe",
            content="<script>alert('xss')</script> and <b>bold</b>",
        )
        response = self.client.get(post.get_absolute_url())
        body = response.content.decode()
        self.assertNotIn("<script>alert('xss')</script>", body)
        self.assertNotIn("<b>bold</b>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_mention_is_linked(self):
        alice = User.objects.create_user("alice", password="pw-alice-123")
        User.objects.create_user("rahul", password="pw-rahul-123")
        post = Post.objects.create(
            author=alice, title="Mentions", content="I learned Django with @rahul"
        )
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, 'href="/@rahul/"')
