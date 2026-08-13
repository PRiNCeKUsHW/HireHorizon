from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from apps.blog.models import Comment, Post
from apps.blog.views import annotate_for_viewer
from apps.core.ratelimit import rate_limit
from apps.notifications.models import Notification

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Follow

User = get_user_model()


# 10 attempts / 5 minutes per IP: generous enough for someone who mistypes a
# password a few times, tight enough to slow credential stuffing.
@method_decorator(rate_limit("login", limit=10, window_seconds=300), name="post")
class HireHorizonLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class HireHorizonLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")


class HireHorizonPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:settings")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been updated.")
        return super().form_valid(form)


# 5 registrations / hour per IP: creating accounts should be rare traffic,
# so this mainly exists to blunt scripted sign-up spam.
@rate_limit("register", limit=5, window_seconds=3600)
def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to HireHorizon, @{user.username}.")
        return redirect("core:home")
    return render(request, "accounts/register.html", {"form": form})


def profile(request, username):
    user = get_object_or_404(
        User.objects.annotate(
            followers_count=Count("followers_set", distinct=True),
            following_count=Count("following_set", distinct=True),
            posts_count=Count(
                "posts",
                distinct=True,
                filter=Q(posts__status=Post.Status.PUBLISHED),
            ),
        ),
        username=username,
    )

    tab = request.GET.get("tab", "posts")
    if tab == "replies":
        items = (
            Comment.objects.filter(author=user)
            .select_related("post", "post__author", "author")
            .order_by("-created_at")
        )
    elif tab == "likes":
        items = annotate_for_viewer(
            Post.objects.published()
            .filter(likes__user=user)
            .for_feed()
            .order_by("-likes__created_at"),
            request.user,
        )
    else:
        tab = "posts"
        queryset = Post.objects.filter(author=user)
        # Drafts are private to their author.
        if request.user != user:
            queryset = queryset.published()
        items = annotate_for_viewer(queryset.for_feed(), request.user)

    page = Paginator(items, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": user,
            "page_obj": page,
            "tab": tab,
            "is_following": request.user.is_authenticated
            and request.user.is_following(user),
            "is_self": request.user == user,
        },
    )


def _follow_list(request, username, direction):
    user = get_object_or_404(User, username=username)
    if direction == "followers":
        people = User.objects.filter(following_set__following=user)
        title = "Followers"
    else:
        people = User.objects.filter(followers_set__follower=user)
        title = "Following"

    people = people.annotate(
        followers_count=Count("followers_set", distinct=True)
    ).order_by("username")
    page = Paginator(people, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/follow_list.html",
        {"profile_user": user, "page_obj": page, "list_title": title},
    )


def followers(request, username):
    return _follow_list(request, username, "followers")


def following(request, username):
    return _follow_list(request, username, "following")


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)

    if target == request.user:
        return JsonResponse({"error": "You cannot follow yourself."}, status=400)

    existing = Follow.objects.filter(follower=request.user, following=target)
    if existing.exists():
        existing.delete()
        is_following = False
    else:
        try:
            Follow.objects.create(follower=request.user, following=target)
        except IntegrityError:
            # Raced with another request; the follow already exists.
            pass
        is_following = True
        Notification.push(
            recipient=target,
            actor=request.user,
            notification_type=Notification.Type.FOLLOW,
        )

    count = Follow.objects.filter(following=target).count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"following": is_following, "followers_count": count})
    return redirect(target.get_absolute_url())


@login_required
def edit_profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect(request.user.get_absolute_url())
    return render(request, "accounts/edit_profile.html", {"form": form})


@login_required
def settings_view(request):
    return render(request, "accounts/settings.html")
