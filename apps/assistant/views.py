import json

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.languages import LANGUAGE_LABELS, normalize_language
from apps.genealogy.access import can_edit, require_edit

from . import actions, gemini
from .context import describe

PER_HOUR = 40
MAX_TEXT = 8000
MAX_TURNS = 20
SALT = "assistant.proposal"


@login_required
def chat(request):
    return render(request, "assistant/chat.html", {"configured": gemini.configured()})


def _history(raw):
    contents = []
    for turn in (raw if isinstance(raw, list) else [])[-MAX_TURNS:]:
        if not isinstance(turn, dict) or turn.get("role") not in ("user", "model"):
            continue
        text = str(turn.get("text", ""))[:MAX_TEXT].strip()
        if text and contents and contents[-1]["role"] == turn["role"]:
            contents[-1]["parts"][0]["text"] += "\n" + text
        elif text:
            contents.append({"role": turn["role"], "parts": [{"text": text}]})
    # Gemini wants the conversation to start with the user.
    while contents and contents[0]["role"] != "user":
        contents.pop(0)
    return contents


def _spend(request):
    """Counts one request to Gemini; False when this hour's share is used up."""
    key = f"assistant:{request.user.pk}"
    used = cache.get(key, 0)
    if used >= PER_HOUR:
        return False
    cache.set(key, used + 1, 3600)
    return True


def _body(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


@login_required
@require_POST
def message(request):
    if not gemini.configured():
        return JsonResponse({"error": _("The assistant is not set up yet.")}, status=400)
    data = _body(request)
    text = str(data.get("message", "")).strip()[:MAX_TEXT]
    if not text:
        return JsonResponse({"error": _("Write a message.")}, status=400)
    if not _spend(request):
        return JsonResponse({"error": _("That is enough for this hour. Please try again a little later.")}, status=429)

    contents = _history(list(data.get("history") or []) + [{"role": "user", "text": text}])
    editing = can_edit(request.user, request.archive)
    try:
        answer = gemini.generate(describe(request), contents, tools=actions.TOOLS if editing else None)
    except gemini.AIError as exc:
        busy = str(exc) == "busy"
        return JsonResponse({"error": _("The assistant is busy. Please try again in a minute.") if busy
                             else _("The assistant could not answer. Please try again.")}, status=502)
    proposals = []
    for call in answer["calls"][:5] if editing else []:
        name, args = call.get("name"), call.get("args") or {}
        if name not in {t["name"] for t in actions.TOOLS} or not isinstance(args, dict):
            continue
        proposals.append({
            "summary": actions.describe(request.archive, name, args),
            "story": str(args.get("story") or args.get("life_story_append") or "")[:MAX_TEXT],
            "token": signing.dumps({"o": request.archive.pk, "n": name, "a": args}, salt=SALT),
        })
    reply = answer["text"] or (_("Here is what I suggest. Check it and press “Add” to save it.") if proposals
                               else _("The assistant could not answer. Please try again."))
    return JsonResponse({"reply": reply, "proposals": proposals})


@login_required
@require_POST
def apply(request):
    try:
        proposal = signing.loads(str(_body(request).get("token", "")), salt=SALT, max_age=24 * 3600)
    except signing.BadSignature:
        return JsonResponse({"error": _("This proposal has expired. Ask again.")}, status=400)
    if proposal.get("o") != request.archive.pk:
        return JsonResponse({"error": _("Access denied.")}, status=403)
    try:
        owner = require_edit(request)
        result = actions.run(owner, request.user, proposal["n"], proposal["a"])
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except actions.Refused as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "message": _("Saved."), "url": result.get_absolute_url()})


@login_required
@require_POST
def transcribe(request):
    """A voice or video message turned into text, to put into a story."""
    from apps.genealogy import recordings

    if not gemini.configured():
        return JsonResponse({"error": _("The assistant is not set up yet.")}, status=400)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": _("This is not a voice or video recording.")}, status=400)
    try:
        content, _kind = recordings.clean(upload)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    if not _spend(request):
        return JsonResponse({"error": _("That is enough for this hour. Please try again a little later.")}, status=429)
    language = LANGUAGE_LABELS.get(normalize_language(get_language()) or settings.LANGUAGE_CODE, "")
    try:
        text = gemini.transcribe(content.read(), content.content_type, language)
    except gemini.AIError:
        return JsonResponse({"error": _("The recording could not be turned into text. Please try again.")}, status=502)
    if not text:
        return JsonResponse({"error": _("No words were heard in the recording.")}, status=400)
    return JsonResponse({"text": text})
