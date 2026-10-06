from django.contrib import admin

from .models import Connection, PersonMatch


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "kind", "status", "created_at", "answered_at")
    list_filter = ("status", "kind")
    raw_id_fields = ("sender", "recipient", "sender_tree", "recipient_tree", "sender_person", "sender_anchor",
                     "recipient_person")


@admin.register(PersonMatch)
class PersonMatchAdmin(admin.ModelAdmin):
    list_display = ("first", "second", "rejected", "decided_by", "created_at")
    raw_id_fields = ("first", "second", "decided_by")
