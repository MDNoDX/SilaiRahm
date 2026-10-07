"""Stories become family events (memories), and the list of event types is shortened.

Every story is kept as an event of the type "Memory or other event" with the
same title, year, text and person. Events of the types that are no longer
offered keep their meaning in the title.
"""
from django.db import migrations, models

OLD_KINDS = {  # removed type -> its old name, kept as the title
    "pregnancy": "Farzand kutilmoqda",
    "graduation": "Oʻqishni tamomlash",
    "work": "Yangi ish",
    "move": "Yangi uyga koʻchish",
    "memorial": "Yil oshi (xotira)",
}


def forwards(apps, schema_editor):
    Story = apps.get_model("genealogy", "Story")
    Event = apps.get_model("genealogy", "Event")
    for event in Event.objects.filter(kind__in=OLD_KINDS):
        if not event.title:
            event.title = OLD_KINDS[event.kind]
        event.kind = "other"
        event.save(update_fields=["title", "kind"])
    for story in Story.objects.all().order_by("created_at"):
        event = Event.objects.create(owner_id=story.owner_id, kind="other", title=story.title[:200],
                                     description=story.body, year=story.year)
        Event.objects.filter(pk=event.pk).update(created_at=story.created_at)
        if story.person_id:
            event.people.add(story.person_id)


class Migration(migrations.Migration):
    dependencies = [("genealogy", "0006_person_linked_user")]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.DeleteModel(name="Story"),
        migrations.AlterField(
            model_name="event", name="kind",
            field=models.CharField(choices=[
                ("wedding", "Wedding"), ("engagement", "Engagement (fotiha)"), ("birth", "Birth of a child"),
                ("beshik", "Cradle celebration (beshik toʻyi)"), ("sunnat", "Circumcision celebration (sunnat toʻyi)"),
                ("aqiqa", "Aqiqa"), ("birthday", "Birthday"), ("hayit", "Eid (hayit)"), ("new_year", "New Year"),
                ("hajj", "Hajj or umrah"), ("anniversary", "Jubilee"), ("death", "Passing away"),
                ("other", "Memory or other event")], default="other", max_length=20, verbose_name="type of event"),
        ),
        migrations.AlterField(
            model_name="event", name="description", field=models.TextField(blank=True, verbose_name="story"),
        ),
    ]
