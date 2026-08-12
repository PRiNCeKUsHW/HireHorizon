from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "subject", "message")
    date_hierarchy = "created_at"
    readonly_fields = ("name", "email", "subject", "message", "created_at")
    actions = ("mark_read", "mark_resolved")

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.READ)
        self.message_user(request, f"{updated} message(s) marked read.")

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.RESOLVED)
        self.message_user(request, f"{updated} message(s) marked resolved.")
