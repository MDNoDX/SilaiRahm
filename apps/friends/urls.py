from django.urls import path

from . import views

app_name = "friends"

urlpatterns = [
    path("", views.friends_list, name="list"),
    path("yangi/", views.contact_create, name="create"),
    path("<int:pk>/tahrirlash/", views.contact_edit, name="edit"),
    path("<int:pk>/ochirish/", views.contact_delete, name="delete"),
]
