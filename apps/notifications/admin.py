from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "actor", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username")
    autocomplete_fields = ("recipient", "actor")
    date_hierarchy = "created_at"
    list_select_related = ("recipient", "actor")
    actions = ("mark_read", "mark_unread")

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} notification(s) marked read.")

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} notification(s) marked unread.")
