from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("post/create/", views.PostCreateView.as_view(), name="post_create"),
    path("post/mine/", views.my_posts, name="my_posts"),
    path("bookmarks/", views.bookmarks, name="bookmarks"),
    path("comment/<int:pk>/edit/", views.edit_comment, name="comment_edit"),
    path("comment/<int:pk>/delete/", views.delete_comment, name="comment_delete"),
    # Slug routes come last so "create"/"mine" are never swallowed by <slug>.
    path("post/<slug:slug>/", views.post_detail, name="post_detail"),
    path("post/<slug:slug>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
    path(
        "post/<slug:slug>/delete/", views.PostDeleteView.as_view(), name="post_delete"
    ),
    path("post/<slug:slug>/like/", views.toggle_like, name="toggle_like"),
    path("post/<slug:slug>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("post/<slug:slug>/repost/", views.toggle_repost, name="toggle_repost"),
    path("post/<slug:slug>/comment/", views.add_comment, name="add_comment"),
]
