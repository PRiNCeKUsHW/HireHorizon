from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.blog.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("messages/", include("apps.messaging.urls")),
]

handler400 = "apps.core.errors.bad_request"
handler403 = "apps.core.errors.permission_denied"
handler404 = "apps.core.errors.page_not_found"
handler500 = "apps.core.errors.server_error"

admin.site.site_header = "HireHorizon administration"
admin.site.site_title = "HireHorizon admin"
admin.site.index_title = "Manage HireHorizon"
