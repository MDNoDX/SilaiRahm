"""Import a JSON export ("Download my data") into a user's archive.

    python manage.py import_archive silairahm-2026-09-30.json --user nodirbek
"""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.genealogy.archive_io import import_archive


class Command(BaseCommand):
    help = "Import a Silai Rahm JSON archive into an existing user's account."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--user", required=True)

    def handle(self, *args, **opts):
        user = get_user_model().objects.filter(username=opts["user"]).first()
        if not user:
            raise CommandError(f"No user {opts['user']!r}.")
        with open(opts["file"], encoding="utf-8") as f:
            data = json.load(f)
        counts = import_archive(user, data)
        self.stdout.write(self.style.SUCCESS(f"Imported: {counts}"))
