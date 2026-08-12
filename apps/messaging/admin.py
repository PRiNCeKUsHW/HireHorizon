from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


class ParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "participant_names", "message_total", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("participants__user__username",)
    inlines = (ParticipantInline,)
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("participants__user")

    @admin.display(description="Participants")
    def participant_names(self, obj):
        return ", ".join(p.user.username for p in obj.participants.all())

    @admin.display(description="Messages")
    def message_total(self, obj):
        return obj.messages.count()


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("conversation", "user", "last_read_at")
    search_fields = ("user__username",)
    autocomplete_fields = ("conversation", "user")
    list_select_related = ("conversation", "user")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "conversation", "short_body", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "sender__username")
    autocomplete_fields = ("conversation", "sender")
    date_hierarchy = "created_at"
    list_select_related = ("sender", "conversation")

    @admin.display(description="Message")
    def short_body(self, obj):
        return obj.body[:60] + ("…" if len(obj.body) > 60 else "")
