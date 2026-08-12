from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    notifications = (
        Notification.objects.filter(recipient=request.user)
        .select_related("actor", "content_type")
        .prefetch_related("related_object")
    )
    page = Paginator(notifications, settings.PAGE_SIZE).get_page(
        request.GET.get("page")
    )
    # Opening the page clears the badge; the rows stay visible either way.
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    return render(request, "notifications/list.html", {"page_obj": page})


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"unread": 0})
    return redirect("notifications:list")
