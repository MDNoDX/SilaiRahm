"""Uploaded files kept inside the database.

On serverless hosting (Vercel) there is no persistent disk, and keeping files
in PostgreSQL means one database backup holds everything: moving to another
server never loses photos. Family archives are small (a few photos per
person), so this is simple and robust.
"""
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


def thumb_name(name):
    """Where the small copy of a photo is kept (made on first request)."""
    return f"thumbs/{name}"


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from .models import StoredFile

        return StoredFile

    def _open(self, name, mode="rb"):
        obj = self._model().objects.get(name=name)
        f = ContentFile(bytes(obj.content), name=name)
        return f

    def _save(self, name, content):
        content.seek(0) if hasattr(content, "seek") else None
        data = content.read()
        content_type = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._model().objects.update_or_create(
            name=name, defaults={"content": data, "size": len(data), "content_type": content_type}
        )
        return name

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def delete(self, name):
        self._model().objects.filter(name__in=[name, thumb_name(name)]).delete()

    def size(self, name):
        obj = self._model().objects.filter(name=name).only("size").first()
        return obj.size if obj else 0

    def url(self, name):
        return reverse("media", args=[name])

    def listdir(self, path):
        prefix = path.rstrip("/") + "/" if path else ""
        names = self._model().objects.filter(name__startswith=prefix).values_list("name", flat=True)
        dirs, files = set(), []
        for n in names:
            rest = n[len(prefix):]
            if "/" in rest:
                dirs.add(rest.split("/", 1)[0])
            else:
                files.append(rest)
        return sorted(dirs), sorted(files)
