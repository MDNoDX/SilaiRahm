"""A small client for Google's Gemini API (the free tier is enough).

Needs GEMINI_API_KEY (Google AI Studio → Get API key). The model can be
changed with GEMINI_MODEL. On the free tier Google may use what is sent to
improve its products; the assistant page says so.
"""
import json
import logging
import time

import requests
from django.conf import settings

log = logging.getLogger(__name__)
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"


class AIError(Exception):
    pass


def configured():
    return bool(settings.GEMINI_API_KEY)


# Google retires model versions; "-latest" follows the newest one. Tried in order when one is gone or busy.
# The Flash-Lite models answer family questions as well as Flash, in about 2 seconds instead of 5–60.
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-latest"]


def _thinking(model):
    """Short thinking keeps answers to a few seconds (the 2.x and 3.x models are told differently)."""
    if model.startswith("gemini-2."):
        return {"thinkingBudget": 0}
    return {"thinkingLevel": "minimal" if "lite" in model else "low"}


def _post(model, body, timeout):
    try:
        return requests.post(URL.format(model=model), json=body, timeout=timeout,
                             headers={"x-goog-api-key": settings.GEMINI_API_KEY})
    except requests.RequestException as exc:
        log.warning("Gemini (%s) could not be reached: %s", model, exc)
        return None


BUDGET = 50  # seconds for one answer, all models together (Vercel stops a request at 60)


def generate(system, contents, tools=None, timeout=25):
    """One answer: {"text": "...", "calls": [{"name": ..., "args": {...}}]}."""
    base = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents}
    if tools:
        base["tools"] = [{"functionDeclarations": tools}]
    models = list(dict.fromkeys([settings.GEMINI_MODEL] + FALLBACK_MODELS))
    response, deadline = None, time.monotonic() + BUDGET
    for model in models:
        left = deadline - time.monotonic()
        if left < 3:
            break
        body = {**base, "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096,
                                             "thinkingConfig": _thinking(model)}}
        response = _post(model, body, min(timeout, left))
        if response is not None and response.status_code == 400 and "hinking" in response.text:
            del body["generationConfig"]["thinkingConfig"]  # a model that does not take this setting
            response = _post(model, body, min(timeout, left))
        if response is not None and response.status_code == 200:
            break
        if response is not None:
            log.warning("Gemini (%s) answered %s: %s", model, response.status_code, response.text[:300])
            if response.status_code not in (404, 429, 500, 503, 504):  # a wrong key or a bad request
                break
    if response is None:
        raise AIError("unreachable")
    if response.status_code == 429:
        raise AIError("busy")
    if response.status_code != 200:
        raise AIError(f"status {response.status_code}")
    data = response.json()
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return {"text": "".join(p.get("text", "") for p in parts if not p.get("thought")).strip(),
            "calls": [p["functionCall"] for p in parts if "functionCall" in p]}


def stream(system, contents, tools=None, first_byte_timeout=20):
    """The answer as it is written: yields ("text", piece) … and finally ("calls", [functionCall, …]).

    Each model gets `first_byte_timeout` seconds to start answering; a busy, retired or silent one is
    skipped for the next. Once text has started, the answer comes from that model to the end."""
    base = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents}
    if tools:
        base["tools"] = [{"functionDeclarations": tools}]
    status, deadline = None, time.monotonic() + BUDGET
    for model in list(dict.fromkeys([settings.GEMINI_MODEL] + FALLBACK_MODELS)):
        left = deadline - time.monotonic()
        if left < 3:
            break
        body = {**base, "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096,
                                             "thinkingConfig": _thinking(model)}}
        try:
            response = requests.post(STREAM_URL.format(model=model), json=body, stream=True,
                                     timeout=(5, min(first_byte_timeout, left)),
                                     headers={"x-goog-api-key": settings.GEMINI_API_KEY})
        except requests.RequestException as exc:
            log.warning("Gemini (%s) did not answer in time: %s", model, exc)
            continue
        status = response.status_code
        if status != 200:
            log.warning("Gemini (%s) answered %s: %s", model, status, response.text[:300])
            if status in (404, 429, 500, 503, 504):  # gone, out of quota (counted per model) or busy
                continue
            break
        calls = []
        response.encoding = "utf-8"  # event streams come without a charset; Uzbek ʻ ʼ need UTF-8
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                chunk = json.loads(line[5:])
                for part in ((chunk.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []:
                    if "functionCall" in part:
                        calls.append(part["functionCall"])
                    elif part.get("text") and not part.get("thought"):
                        yield "text", part["text"]
        except (requests.RequestException, ValueError) as exc:
            log.warning("Gemini (%s) stopped in the middle: %s", model, exc)
            raise AIError("broken") from exc
        yield "calls", calls
        return
    raise AIError("busy" if status in (429, 503) else f"status {status}")


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
    return generate("You turn family members' spoken stories into written text.", contents, timeout=30)["text"]
