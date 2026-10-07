from django.contrib import admin

from .models import Change, Event, Marriage, Media, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "owner", "gender", "birth_year", "death_year")
    search_fields = ("first_name", "last_name", "search_key")
    list_filter = ("gender",)
    raw_id_fields = ("father", "mother", "owner")


admin.site.register(Marriage)
admin.site.register(Event)


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("person", "kind", "caption", "year", "uploaded_by")
    list_filter = ("kind",)
    raw_id_fields = ("owner", "person", "uploaded_by")


@admin.register(Change)
class ChangeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "actor", "action", "subject", "undone_at")
    list_filter = ("action",)
    raw_id_fields = ("owner", "actor", "person")
