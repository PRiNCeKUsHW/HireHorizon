from django.contrib import admin

from .models import Bookmark, Comment, Like, Post, PostView, Repost


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "status", "created_at", "likes_total", "views_total")
    list_filter = ("status", "created_at", "author")
    search_fields = ("title", "content", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author",)
    date_hierarchy = "created_at"
    list_select_related = ("author",)
    actions = ("publish_selected", "unpublish_selected")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author").with_counts()

    @admin.display(description="Likes", ordering="like_count")
    def likes_total(self, obj):
        return obj.like_count

    @admin.display(description="Views", ordering="view_count")
    def views_total(self, obj):
        return obj.view_count

    @admin.action(description="Publish selected posts")
    def publish_selected(self, request, queryset):
        updated = queryset.update(status=Post.Status.PUBLISHED)
        self.message_user(request, f"{updated} post(s) published.")

    @admin.action(description="Move selected posts to draft")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(status=Post.Status.DRAFT)
        self.message_user(request, f"{updated} post(s) moved to draft.")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "post", "short_body", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "author__username", "post__title")
    autocomplete_fields = ("author", "post", "parent")
    date_hierarchy = "created_at"
    list_select_related = ("author", "post")

    @admin.display(description="Comment")
    def short_body(self, obj):
        return obj.body[:60] + ("…" if len(obj.body) > 60 else "")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "post__title")
    autocomplete_fields = ("user", "post")
    list_select_related = ("user", "post")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "post__title")
    autocomplete_fields = ("user", "post")
    list_select_related = ("user", "post")


@admin.register(Repost)
class RepostAdmin(admin.ModelAdmin):
    list_display = ("reposted_by", "original_post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("reposted_by__username", "original_post__title")
    autocomplete_fields = ("reposted_by", "original_post")
    list_select_related = ("reposted_by", "original_post")


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "session_key", "created_at")
    list_filter = ("created_at",)
    search_fields = ("post__title", "user__username")
    list_select_related = ("post", "user")
    readonly_fields = ("post", "user", "session_key", "created_at")
