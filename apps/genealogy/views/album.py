"""Album: photos, documents, voice recordings and videos of a person."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .. import history, recordings
from ..access import person_for_edit, require_edit
from ..models import Change, Media


MEDIA_MAX_BYTES = 12 * 1024 * 1024
DOCUMENT_TYPES = ("application/pdf",)


@require_POST
@login_required
def media_upload(request, pk):
    from django.core.files.base import ContentFile

    from apps.core.images import shrink

    person = person_for_edit(request, pk)
    added = 0
    for upload in request.FILES.getlist("files")[:20]:
        if upload.size > MEDIA_MAX_BYTES:
            messages.error(request, _("“{name}” is too large.").format(name=upload.name))
            continue
        kind, content = None, None
        ctype = (upload.content_type or "").lower()
        if ctype.startswith("image/"):
            small = shrink(upload)
            if small:
                content, ext = small
                content.name = f"photo.{ext}"
                kind = Media.Kind.PHOTO
        elif ctype.startswith(("audio/", "video/")):
            try:
                content, kind = recordings.clean(upload)
            except ValidationError as exc:
                messages.error(request, _("“{name}”: {error}").format(name=upload.name, error=exc.messages[0]))
                continue
        elif ctype in DOCUMENT_TYPES:
            kind, content = Media.Kind.DOCUMENT, ContentFile(upload.read(), name=upload.name)
        if kind is None:
            messages.error(request, _("“{name}” is not a photo, a PDF document, a voice recording or a video.").format(name=upload.name))
            continue
        year = request.POST.get("year", "")
        Media.objects.create(owner=person.owner, person=person, kind=kind, file=content,
                             caption=request.POST.get("caption", "").strip()[:200],
                             year=int(year) if year.isdigit() and 1000 <= int(year) <= 2200 else None,
                             uploaded_by=request.user)
        added += 1
    if added:
        history.record(person.owner, request.user, Change.Action.UPDATED, person, what="album",
                       details={"added": added})
        messages.success(request, _("Added to the album."))
    return redirect(person.get_absolute_url() + "#album")


def _media_for_edit(request, pk):
    item = get_object_or_404(Media.objects.select_related("person", "owner"), pk=pk)
    require_edit(request, item.owner)
    return item


@require_POST
@login_required
def media_delete(request, pk):
    item = _media_for_edit(request, pk)
    person = item.person
    if person.photo and person.photo.name == item.file.name:
        person.photo = ""
        person.save(update_fields=["photo", "updated_at"])
    item.file.delete(save=False)
    item.delete()
    messages.success(request, _("The record has been deleted."))
    return redirect(person.get_absolute_url() + "#album")


@require_POST
@login_required
def media_portrait(request, pk):
    """Use an album photo as the person's main photo."""
    item = _media_for_edit(request, pk)
    if item.kind == Media.Kind.PHOTO:
        before = history.snapshot(item.person)
        item.person.photo = item.file.name
        item.person.save(update_fields=["photo", "updated_at"])
        history.record_update(request.user, item.person, before)
        messages.success(request, _("The information has been saved."))
    return redirect(item.person)
