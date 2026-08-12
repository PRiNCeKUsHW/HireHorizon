from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from apps.core.utils import notify_mentions
from apps.notifications.models import Notification

from .forms import CommentForm, PostForm
from .models import Bookmark, Comment, Like, Post, PostView, Repost


def annotate_for_viewer(queryset, user):
    """Add liked/bookmarked/reposted flags for the current viewer.

    Uses Exists() subqueries so a feed page stays at a constant number of
    queries no matter how many posts it renders.
    """
    if not user.is_authenticated:
        return queryset
    return queryset.annotate(
        liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=user)),
        bookmarked_by_me=Exists(
            Bookmark.objects.filter(post=OuterRef("pk"), user=user)
        ),
        reposted_by_me=Exists(
            Repost.objects.filter(original_post=OuterRef("pk"), reposted_by=user)
        ),
    )


def record_view(request, post):
    """Count one view per user (or per anonymous session) per post.

    Uniqueness is enforced by the database, so a refresh, a second tab or a
    visit next week all collapse into the single row created the first time.
    """
    try:
        if request.user.is_authenticated:
            PostView.objects.get_or_create(post=post, user=request.user)
        else:
            if not request.session.session_key:
                request.session.save()
            PostView.objects.get_or_create(
                post=post, user=None, session_key=request.session.session_key
            )
    except IntegrityError:
        # Two concurrent requests raced to insert the same row; the row exists
        # either way, which is all this function promises.
        pass


def post_detail(request, slug):
    post = get_object_or_404(
        annotate_for_viewer(Post.objects.for_feed(), request.user), slug=slug
    )

    # Drafts are visible only to their author.
    if not post.is_published and post.author != request.user:
        raise PermissionDenied("This post is not published.")

    if post.is_published:
        record_view(request, post)

    comments = (
        post.comments.filter(parent__isnull=True)
        .select_related("author")
        .prefetch_related(
            Prefetch(
                "replies",
                queryset=Comment.objects.select_related("author").order_by("created_at"),
            )
        )
        .order_by("created_at")
    )

    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": CommentForm(),
            # Re-read after record_view so the number shown includes this visit.
            "view_total": post.views.count(),
        },
    )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        if self.object.is_published:
            notify_mentions(
                text=self.object.content,
                actor=self.request.user,
                related_object=self.object,
            )
        messages.success(self.request, "Post published." if self.object.is_published else "Draft saved.")
        return response


class OwnerOnlyMixin(LoginRequiredMixin):
    """403 unless the logged-in user owns the object.

    Checked on GET and POST alike, so a crafted request cannot bypass a
    template that simply hides the button.
    """

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.author != self.request.user:
            raise PermissionDenied("You can only modify your own content.")
        return obj


class PostUpdateView(OwnerOnlyMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(is_edit=True, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Post updated.")
        return super().form_valid(form)


class PostDeleteView(OwnerOnlyMixin, DeleteView):
    model = Post
    template_name = "blog/post_confirm_delete.html"
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        messages.success(self.request, "Post deleted.")
        return super().form_valid(form)


@login_required
def my_posts(request):
    posts = annotate_for_viewer(
        Post.objects.filter(author=request.user).for_feed(), request.user
    )
    page = Paginator(posts, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "blog/my_posts.html", {"page_obj": page})


def _toggle(model, **lookup):
    """Create or delete a per-user row, returning whether it now exists."""
    existing = model.objects.filter(**lookup)
    if existing.exists():
        existing.delete()
        return False
    try:
        model.objects.create(**lookup)
    except IntegrityError:
        pass
    return True


@login_required
@require_POST
def toggle_like(request, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    liked = _toggle(Like, user=request.user, post=post)
    if liked:
        Notification.push(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.Type.LIKE,
            related_object=post,
        )
    count = post.likes.count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"liked": liked, "count": count})
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def toggle_bookmark(request, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    bookmarked = _toggle(Bookmark, user=request.user, post=post)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"bookmarked": bookmarked})
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def toggle_repost(request, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    reposted = _toggle(Repost, original_post=post, reposted_by=request.user)
    if reposted:
        Notification.push(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.Type.REPOST,
            related_object=post,
        )
    count = post.reposts.count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"reposted": reposted, "count": count})
    return redirect(post.get_absolute_url())


@login_required
def bookmarks(request):
    posts = annotate_for_viewer(
        Post.objects.published().filter(bookmarks__user=request.user).for_feed(),
        request.user,
    ).order_by("-bookmarks__created_at")
    page = Paginator(posts, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "blog/bookmarks.html", {"page_obj": page})


@login_required
@require_POST
def add_comment(request, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    form = CommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Your reply could not be posted.")
        return redirect(post.get_absolute_url())

    comment = form.save(commit=False)
    comment.post = post
    comment.author = request.user

    parent_id = request.POST.get("parent")
    if parent_id:
        # A reply must belong to the same post, otherwise it could be attached
        # to an unrelated thread by editing the form.
        comment.parent = get_object_or_404(Comment, pk=parent_id, post=post)
    comment.save()

    if comment.parent and comment.parent.author != request.user:
        Notification.push(
            recipient=comment.parent.author,
            actor=request.user,
            notification_type=Notification.Type.REPLY,
            related_object=post,
        )
    else:
        Notification.push(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.Type.COMMENT,
            related_object=post,
        )
    notify_mentions(text=comment.body, actor=request.user, related_object=post)

    messages.success(request, "Reply posted.")
    return redirect(f"{post.get_absolute_url()}#comment-{comment.pk}")


@login_required
def edit_comment(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=pk)
    if comment.author != request.user:
        raise PermissionDenied("You can only edit your own comments.")

    form = CommentForm(request.POST or None, instance=comment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reply updated.")
        return redirect(comment.post.get_absolute_url())
    return render(request, "blog/comment_form.html", {"form": form, "comment": comment})


@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=pk)
    if comment.author != request.user:
        raise PermissionDenied("You can only delete your own comments.")
    url = comment.post.get_absolute_url()
    comment.delete()
    messages.success(request, "Reply deleted.")
    return redirect(url)
