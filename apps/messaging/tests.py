from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.messaging.models import Conversation, Message

User = get_user_model()


class MessagingTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-12345")
        self.mallory = User.objects.create_user("mallory", password="pw-mall-12345")
        self.conversation = Conversation.start(self.alice, self.bob)

    def test_start_is_idempotent(self):
        again = Conversation.start(self.alice, self.bob)
        self.assertEqual(self.conversation.pk, again.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_send_and_receive(self):
        self.client.force_login(self.alice)
        self.client.post(
            reverse("messaging:conversation", args=[self.conversation.pk]),
            {"body": "Hello Bob"},
        )
        self.assertEqual(Message.objects.count(), 1)

        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("messaging:conversation", args=[self.conversation.pk])
        )
        self.assertContains(response, "Hello Bob")

    def test_outsider_cannot_read_conversation(self):
        Message.objects.create(
            conversation=self.conversation, sender=self.alice, body="private words"
        )
        self.client.force_login(self.mallory)
        response = self.client.get(
            reverse("messaging:conversation", args=[self.conversation.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_post_into_conversation(self):
        self.client.force_login(self.mallory)
        response = self.client.post(
            reverse("messaging:conversation", args=[self.conversation.pk]),
            {"body": "intruding"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(
            reverse("messaging:conversation", args=[self.conversation.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_cannot_message_yourself(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("messaging:start", args=["alice"]))
        self.assertEqual(response.status_code, 403)

    def test_inbox_lists_conversation(self):
        Message.objects.create(
            conversation=self.conversation, sender=self.alice, body="latest line"
        )
        self.client.force_login(self.bob)
        response = self.client.get(reverse("messaging:inbox"))
        self.assertContains(response, "latest line")
