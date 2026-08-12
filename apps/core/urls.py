from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("explore/", views.explore, name="explore"),
    path("search/", views.search, name="search"),
    path("contact/", views.contact, name="contact"),
    path("about/", views.about, name="about"),
]
