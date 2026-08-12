from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Follow
from apps.blog.models import Post
from apps.blog.views import annotate_for_viewer

from .forms import ContactForm

User = get_user_model()


def home(request):
    """Landing page for visitors, personalised feed for signed-in users."""
    if not request.user.is_authenticated:
        latest = Post.objects.published().for_feed()[:6]
        return render(request, "core/landing.html", {"latest_posts": latest})

    # Posts by people you follow, plus your own.
    followed_ids = Follow.objects.filter(follower=request.user).values("following_id")
    feed = annotate_for_viewer(
        Post.objects.published()
        .filter(Q(author__in=followed_ids) | Q(author=request.user))
        .for_feed(),
        request.user,
    )
    page = Paginator(feed, settings.PAGE_SIZE).get_page(request.GET.get("page"))

    suggestions = []
    if not page.object_list:
        # Empty feed: help the user find someone to follow.
        suggestions = (
            User.objects.exclude(pk=request.user.pk)
            .exclude(pk__in=followed_ids)
            .annotate(followers_count=Count("followers_set"))
            .order_by("-followers_count")[:5]
        )

    return render(
        request, "core/feed.html", {"page_obj": page, "suggestions": suggestions}
    )


def explore(request):
    """Public discovery: trending, latest, and people to follow."""
    tab = request.GET.get("tab", "trending")
    base = annotate_for_viewer(Post.objects.published().for_feed(), request.user)

    if tab == "latest":
        posts = base.order_by("-created_at")
    else:
        tab = "trending"
        # Simple, predictable ranking: engagement over the last week, then
        # recency. Deliberately not a magic score nobody can reason about.
        since = timezone.now() - timezone.timedelta(days=7)
        posts = base.filter(created_at__gte=since).order_by(
            "-like_count", "-comment_count", "-created_at"
        )
        if not posts.exists():
            posts = base.order_by("-like_count", "-created_at")

    page = Paginator(posts, settings.PAGE_SIZE).get_page(request.GET.get("page"))

    people = (
        User.objects.annotate(
            followers_count=Count("followers_set", distinct=True),
            posts_count=Count("posts", distinct=True),
        )
        .filter(posts_count__gt=0)
        .order_by("-followers_count", "-posts_count")[:5]
    )
    if request.user.is_authenticated:
        people = [p for p in people if p != request.user]

    return render(
        request, "core/explore.html", {"page_obj": page, "tab": tab, "people": people}
    )


def search(request):
    """Search people and posts. Two tabs, one query box."""
    query = (request.GET.get("q") or "").strip()
    tab = request.GET.get("tab", "posts")

    people = User.objects.none()
    posts = Post.objects.none()

    if query:
        if tab == "people":
            people = (
                User.objects.filter(
                    Q(username__icontains=query)
                    | Q(display_name__icontains=query)
                    | Q(bio__icontains=query)
                )
                .annotate(followers_count=Count("followers_set", distinct=True))
                .order_by("-followers_count")
            )
        else:
            tab = "posts"
            posts = annotate_for_viewer(
                Post.objects.published()
                .filter(Q(title__icontains=query) | Q(content__icontains=query))
                .for_feed(),
                request.user,
            ).order_by("-created_at")

    results = people if tab == "people" else posts
    page = Paginator(results, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request, "core/search.html", {"page_obj": page, "query": query, "tab": tab}
    )


def contact(request):
    """Contact form. Saves to the database — the site sends no email."""
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        flash.success(
            request, "Thanks — your message has been received. We'll get back to you."
        )
        return redirect("core:contact")
    return render(request, "core/contact.html", {"form": form})


def about(request):
    return render(request, "core/about.html")
