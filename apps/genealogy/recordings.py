"""Voice and video messages: a story told aloud instead of (or as well as) written.

Recorded in the browser (or chosen from the phone) and kept like album files.
Vercel accepts request bodies of up to 4.5 MB, so one message is limited to
4 MB; the recorder keeps its bit rate low (about 25 minutes of voice or
1 minute of video).
"""
import mimetypes

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

MAX_BYTES = 4 * 1024 * 1024
EXTENSIONS = {
    "audio/webm": "weba", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
    "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav",
    "video/webm": "webm", "video/mp4": "mp4", "video/quicktime": "mov", "video/3gpp": "3gp",
}
AUDIO_EXTENSIONS = {"weba", "ogg", "m4a", "aac", "mp3", "wav", "oga"}
VIDEO_EXTENSIONS = {"mp4", "mov", "3gp", "webm"}


def kind_of(name):
    """"audio" or "video" from a stored name (voice in webm is kept as *.weba)."""
    ext = (name or "").lower().rsplit(".", 1)[-1]
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return "video" if ext in VIDEO_EXTENSIONS else ""


def clean(upload):
    """A checked recording ready to store, and its kind: (ContentFile, "audio" | "video")."""
    ctype = (getattr(upload, "content_type", "") or "").split(";")[0].strip().lower()
    if upload.size > MAX_BYTES:
        raise ValidationError(_("The recording is too long: up to 4 MB (about 25 minutes of voice or 1 minute of video)."))
    if ctype not in EXTENSIONS:  # some phones send no type: go by the file name
        guessed = mimetypes.guess_type(getattr(upload, "name", "") or "")[0] or ""
        ctype = {"audio/mp4a-latm": "audio/mp4", "audio/x-aac": "audio/aac"}.get(guessed, guessed)
    if ctype not in EXTENSIONS:
        raise ValidationError(_("This is not a voice or video recording."))
    kind = "audio" if ctype.startswith("audio/") else "video"
    upload.seek(0)
    content = ContentFile(upload.read(), name=f"recording.{EXTENSIONS[ctype]}")
    content.content_type = ctype  # served back exactly as recorded (the storage reads this)
    return content, kind
