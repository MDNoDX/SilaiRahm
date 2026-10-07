from django.urls import path

from . import views

app_name = "network"

urlpatterns = [
    path("", views.index, name="index"),
    path("qidiruv.json", views.search_json, name="search_json"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("u/<str:username>/obuna/", views.follow_view, name="follow"),
    path("u/<str:username>/obunachi/olib-tashlash/", views.follower_remove, name="follower_remove"),
    path("obuna/<int:pk>/javob/", views.follow_answer, name="follow_answer"),
    path("odam/<str:username>/", views.request_view, name="request"),
    path("<int:pk>/", views.connection_view, name="connection"),
    path("<int:pk>/javob/", views.answer, name="answer"),
    path("<int:pk>/bekor/", views.cancel, name="cancel"),
    path("<int:pk>/uzish/", views.disconnect, name="disconnect"),
    path("birlashtirish/", views.merge_view, name="merge"),
    path("moslik/", views.match, name="match"),
]
