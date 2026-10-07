from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("xabar/", views.message, name="message"),
    path("saqlash/", views.apply, name="apply"),
    path("matnga/", views.transcribe, name="transcribe"),
]
