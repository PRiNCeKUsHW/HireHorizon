from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.notifications.models import Notification

from .forms import MessageForm
from .models import Conversation, ConversationParticipant, Message

User = get_user_model()


@login_required
def inbox(request):
    conversations = (
        Conversation.objects.filter(participants__user=request.user)
        .prefetch_related(
            Prefetch(
                "participants",
                queryset=ConversationParticipant.objects.select_related("user"),
            )
        )
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-last_message_at")
    )

    # Latest message per thread in two queries total (works on SQLite and
    # Postgres alike), instead of one query per conversation in the loop.
    last_ids = (
        Message.objects.filter(conversation__in=conversations)
        .values("conversation")
        .annotate(last_id=Max("id"))
        .values_list("last_id", flat=True)
    )
    latest = {
        m.conversation_id: m
        for m in Message.objects.filter(id__in=list(last_ids)).select_related("sender")
    }

    threads = [
        {
            "conversation": conversation,
            "other": conversation.other_participant(request.user),
            "last": latest.get(conversation.pk),
        }
        for conversation in conversations
    ]
    return render(request, "messaging/inbox.html", {"threads": threads})


def _participant_or_403(request, conversation):
    """Object-level check: only participants may read a conversation."""
    participant = ConversationParticipant.objects.filter(
        conversation=conversation, user=request.user
    ).first()
    if participant is None:
        raise PermissionDenied("You are not part of this conversation.")
    return participant


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    participant = _participant_or_403(request, conversation)

    form = MessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.conversation = conversation
        message.sender = request.user
        message.save()
        conversation.save(update_fields=["updated_at"])

        other = conversation.other_participant(request.user)
        Notification.push(
            recipient=other,
            actor=request.user,
            notification_type=Notification.Type.MESSAGE,
        )
        return redirect("messaging:conversation", pk=conversation.pk)

    participant.mark_read()
    messages_qs = conversation.messages.select_related("sender").order_by("created_at")
    return render(
        request,
        "messaging/conversation.html",
        {
            "conversation": conversation,
            "chat_messages": messages_qs,
            "other": conversation.other_participant(request.user),
            "form": form,
        },
    )


@login_required
@require_POST
def start_conversation(request, username):
    other = get_object_or_404(User, username=username)
    if other == request.user:
        raise PermissionDenied("You cannot message yourself.")
    conversation = Conversation.start(request.user, other)
    return redirect("messaging:conversation", pk=conversation.pk)
