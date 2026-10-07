"""A small client for Google's Gemini API (the free tier is enough).

Needs GEMINI_API_KEY (Google AI Studio → Get API key). The model can be
changed with GEMINI_MODEL. On the free tier Google may use what is sent to
improve its products; the assistant page says so.
"""
import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(Exception):
    pass


def configured():
    return bool(settings.GEMINI_API_KEY)


def generate(system, contents, tools=None, timeout=45):
    """One answer: {"text": "...", "calls": [{"name": ..., "args": {...}}]}."""
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096}}
    if settings.GEMINI_MODEL.startswith("gemini-2.5-flash"):
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}  # answers in a few seconds
    if tools:
        body["tools"] = [{"functionDeclarations": tools}]
    try:
        response = requests.post(URL.format(model=settings.GEMINI_MODEL), json=body, timeout=timeout,
                                 headers={"x-goog-api-key": settings.GEMINI_API_KEY})
    except requests.RequestException as exc:
        raise AIError(str(exc)) from exc
    if response.status_code == 429:
        raise AIError("busy")
    if response.status_code != 200:
        log.warning("Gemini answered %s: %s", response.status_code, response.text[:300])
        raise AIError(f"status {response.status_code}")
    data = response.json()
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return {"text": "".join(p.get("text", "") for p in parts).strip(),
            "calls": [p["functionCall"] for p in parts if "functionCall" in p]}


# Containers Gemini reads: a voice message in webm goes as video/webm (its sound is understood the same way).
GEMINI_TYPES = {"audio/webm": "video/webm", "audio/mp4": "video/mp4", "audio/x-m4a": "video/mp4",
                "audio/mpeg": "audio/mp3", "audio/x-wav": "audio/wav", "audio/wave": "audio/wav",
                "video/quicktime": "video/mov"}


def transcribe(data, mime, language):
    """The words of a voice or video message, as written text."""
    import base64

    prompt = (f"Write down what is said in this recording as clean, readable text in the language it is spoken in "
              f"(the user's interface language is {language}). Keep every word and the speaker's own way of "
              "telling; add punctuation and paragraphs; leave out only filler sounds. If nothing is said, answer "
              "with an empty text. Answer with the text only.")
    contents = [{"role": "user", "parts": [
        {"inlineData": {"mimeType": GEMINI_TYPES.get(mime, mime), "data": base64.b64encode(data).decode()}},
        {"text": prompt}]}]
    return generate("You turn family members' spoken stories into written text.", contents, timeout=55)["text"]
