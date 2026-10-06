from django.urls import path

from . import views

app_name = "network"

urlpatterns = [
    path("", views.index, name="index"),
    path("odam/<str:username>/", views.request_view, name="request"),
    path("<int:pk>/", views.connection_view, name="connection"),
    path("<int:pk>/javob/", views.answer, name="answer"),
    path("<int:pk>/bekor/", views.cancel, name="cancel"),
    path("<int:pk>/uzish/", views.disconnect, name="disconnect"),
    path("birlashtirish/", views.merge_view, name="merge"),
    path("moslik/", views.match, name="match"),
]
