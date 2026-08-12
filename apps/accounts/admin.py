from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Follow, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "display_name",
        "email",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "display_name", "email", "bio")
    ordering = ("-date_joined",)

    # Same as Django's default, plus the HireHorizon profile fields. There is
    # no avatar field: profile pictures are rendered from initials.
    fieldsets = BaseUserAdmin.fieldsets + (
        ("HireHorizon profile", {"fields": ("display_name", "bio", "location", "website")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("HireHorizon profile", {"fields": ("display_name", "bio")}),
    )


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    list_filter = ("created_at",)
    search_fields = ("follower__username", "following__username")
    autocomplete_fields = ("follower", "following")
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("follower", "following")
