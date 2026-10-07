"""The whole database as one JSON document (for `manage.py loaddata` on any
server): users, archives, photos (they live in the database), settings."""
import gzip
import io

from django.core.management import call_command
from django.utils import timezone


def dump_json():
    buf = io.StringIO()
    call_command("dumpdata", "--natural-foreign", "--natural-primary", "--exclude=contenttypes",
                 "--exclude=auth.permission", "--exclude=admin.logentry", "--exclude=sessions", stdout=buf)
    return buf.getvalue()


def filename(extension="json"):
    return f"silairahm-full-backup-{timezone.localdate().isoformat()}.{extension}"


def dump_gzip():
    return gzip.compress(dump_json().encode("utf-8"), compresslevel=9)
