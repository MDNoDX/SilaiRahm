from django.urls import path

from . import views

app_name = "genealogy"

urlpatterns = [
    # People (views/people.py)
    path("qarindoshlar/", views.people_list, name="people"),
    path("qarindoshlar/yangi/", views.person_create, name="person_create"),
    path("qarindoshlar/<int:pk>/", views.person_detail, name="person"),
    path("qarindoshlar/<int:pk>/tahrirlash/", views.person_edit, name="person_edit"),
    path("qarindoshlar/<int:pk>/ochirish/", views.person_delete, name="person_delete"),
    path("qarindoshlar/<int:pk>/qarindosh-qoshish/", views.relative_add, name="relative_add"),
    path("qarindoshlar/<int:pk>/men/", views.set_self, name="set_self"),
    path("qarindoshlar/<int:pk>/pdf/", views.person_pdf, name="person_pdf"),
    path("qarindoshlar/<int:pk>/hayot-tarixi/", views.person_story, name="person_story"),
    path("nikoh/<int:pk>/", views.marriage_edit, name="marriage_edit"),

    # Album (views/album.py)
    path("qarindoshlar/<int:pk>/albom/", views.media_upload, name="media_upload"),
    path("albom/<int:pk>/ochirish/", views.media_delete, name="media_delete"),
    path("albom/<int:pk>/asosiy/", views.media_portrait, name="media_portrait"),

    # Duplicates, history and undo (views/changes.py)
    path("qarindoshlar/dublikatlar/", views.duplicates_page, name="duplicates"),
    path("qarindoshlar/birlashtirish/", views.merge_people, name="merge"),
    path("tarix/", views.history_page, name="history"),
    path("tarix/<int:pk>/qaytarish/", views.history_undo, name="history_undo"),

    # Family tree (views/tree.py)
    path("shajara/", views.tree_page, name="tree"),
    path("shajara/kitob.pdf", views.family_book, name="family_book"),
    path("shajara/kitob/", views.book_page, name="book"),
    path("shajara/<str:username>/", views.tree_page, name="tree_for"),
    path("shajara/<str:username>/malumot.json", views.tree_data, name="tree_data_for"),
    path("shajara/<str:username>/shajara.pdf", views.tree_pdf, name="tree_pdf_for"),
    path("shajara/<str:username>/kitob.pdf", views.family_book, name="family_book_for"),
    path("qarindoshlar/<int:pk>/karta.json", views.person_card, name="person_card"),
    path("qarindoshlar/<int:pk>/tezkor/", views.quick_add, name="quick_add"),

    # Timeline (views/timeline.py)
    path("vaqt-chizigi/", views.timeline, name="timeline"),

    # Events (views/events.py)
    path("voqealar/", views.upcoming, name="upcoming"),
    path("voqealar/yangi/", views.event_create, name="event_create"),
    path("voqealar/<int:pk>/", views.event_detail, name="event"),
    path("voqealar/<int:pk>/tahrirlash/", views.event_edit, name="event_edit"),
    path("voqealar/<int:pk>/ochirish/", views.event_delete, name="event_delete"),


    # Search (views/search.py)
    path("qidiruv/", views.search, name="search"),
    path("qidiruv/tez/", views.search_json, name="search_json"),

    # "Who is who to whom?" (views/calculator.py)
    path("kim-kimga-kim/", views.calculator, name="calculator"),

    # Export and import (views/exchange.py)
    path("shajara/eksport.ged", views.gedcom_export, name="gedcom"),
    path("shajara/eksport.json", views.archive_export, name="archive_export"),
    path("shajara/import.ged", views.gedcom_import, name="gedcom_import"),
]
