"""Write the JavaScript translation catalogues as static files.

    python manage.py build_js_catalogs

One file per language (static/js/i18n/uz.js, uz-cyrl.js, ru.js, en.js). Pages
load the file of their language from the CDN, cached for a year, instead of
asking the server for /jsi18n/ on every page view. Run it after
compilemessages; tests/test_i18n.py checks the files are up to date.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.utils import translation
from django.views.i18n import JavaScriptCatalog

OUT = Path(settings.BASE_DIR) / "static" / "js" / "i18n"


def catalogue(code):
    with translation.override(code):
        response = JavaScriptCatalog.as_view(packages=["apps.core"])(RequestFactory().get("/"))
    return response.content


class Command(BaseCommand):
    help = "Write static/js/i18n/<language>.js for every language of the site."

    def handle(self, *args, **options):
        OUT.mkdir(parents=True, exist_ok=True)
        for code, _name in settings.LANGUAGES:
            (OUT / f"{code}.js").write_bytes(catalogue(code))
            self.stdout.write(f"static/js/i18n/{code}.js")
