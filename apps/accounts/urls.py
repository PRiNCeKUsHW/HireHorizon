from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.HireHorizonLoginView.as_view(), name="login"),
    path("logout/", views.HireHorizonLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/profile/", views.edit_profile, name="edit_profile"),
    path(
        "settings/password/",
        views.HireHorizonPasswordChangeView.as_view(),
        name="password_change",
    ),
    # Profile routes use the @username form people expect from social sites.
    # They only match paths beginning with "@", so they cannot shadow anything.
    path("@<str:username>/", views.profile, name="profile"),
    path("@<str:username>/followers/", views.followers, name="followers"),
    path("@<str:username>/following/", views.following, name="following"),
    path("@<str:username>/follow/", views.toggle_follow, name="toggle_follow"),
]
