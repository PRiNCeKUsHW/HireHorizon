from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("<int:pk>/", views.conversation_detail, name="conversation"),
    path("start/<str:username>/", views.start_conversation, name="start"),
]
