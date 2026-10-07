"""Follow and privacy, voice/video stories and the AI assistant (with Gemini mocked)."""
import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.genealogy.models import Event, Media, Person
from apps.network.models import Follow

from .helpers import make_family

VOICE = b"\x1aE\xdf\xa3" + b"0" * 2000  # looks like a small webm


def account(username, first_name="Aziz"):
    """A user who has finished signing up (has their own record)."""
    user = User.objects.create_user(username, f"{username}@example.com", "x-parol-2026", first_name=first_name,
                                    gender="male")
    user.person = Person.objects.create(owner=user, first_name=first_name, gender="male")
    user.save(update_fields=["person"])
    return user


class FollowPrivacyTests(TestCase):
    def setUp(self):
        self.owner, self.p = make_family()
        self.other = account("aziz")
        self.client.force_login(self.other)

    def test_private_account_needs_approval(self):
        self.owner.private_account, self.owner.tree_audience = True, "followers"
        self.owner.save()
        tree = reverse("genealogy:tree_for", args=[self.owner.username])
        self.assertEqual(self.client.get(tree).status_code, 403)
        self.client.post(reverse("network:follow", args=[self.owner.username]))
        item = Follow.objects.get(follower=self.other, followed=self.owner)
        self.assertFalse(item.approved)
        self.assertEqual(self.client.get(tree).status_code, 403)
        self.client.force_login(self.owner)
        self.client.post(reverse("network:follow_answer", args=[item.pk]), {"approve": "1"})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(tree).status_code, 200)
        # Stories stay with the family unless the owner opens them.
        person = reverse("genealogy:person", args=[self.p["me"].pk])
        self.assertNotContains(self.client.get(person), 'id="life-edit"')

    def test_public_account_follows_at_once_and_unfollow(self):
        self.owner.private_account = False
        self.owner.save()
        self.client.post(reverse("network:follow", args=[self.owner.username]))
        self.assertTrue(Follow.objects.get(follower=self.other, followed=self.owner).approved)
        self.client.post(reverse("network:follow", args=[self.owner.username]), {"stop": "1"})
        self.assertFalse(Follow.objects.filter(follower=self.other).exists())

    def test_public_tree_and_profile(self):
        self.owner.tree_audience = "public"
        self.owner.save()
        self.assertEqual(self.client.get(reverse("genealogy:tree_for", args=[self.owner.username])).status_code, 200)
        page = self.client.get(reverse("network:profile", args=[self.owner.username]))
        self.assertContains(page, self.owner.first_name)

    def test_cannot_follow_yourself(self):
        self.client.post(reverse("network:follow", args=[self.other.username]))
        self.assertFalse(Follow.objects.exists())

    def test_live_search(self):
        response = self.client.get(reverse("network:search_json") + "?q=Tim")
        self.assertEqual(response.status_code, 200)


class RecordingTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def _voice(self, name="message.weba", ctype="audio/webm"):
        return SimpleUploadedFile(name, VOICE, content_type=ctype)

    def test_event_told_aloud(self):
        response = self.client.post(reverse("genealogy:event_create"), {
            "kind": "other", "title": "Bogʻdagi kun", "people": [self.p["me"].pk], "description": "",
            "recording": self._voice()})
        event = Event.objects.get()
        self.assertRedirects(response, event.get_absolute_url())
        self.assertEqual(event.recording_kind, "audio")
        page = self.client.get(event.get_absolute_url())
        self.assertContains(page, "<audio")
        # Played from any point: Safari asks for byte ranges.
        media = self.client.get(event.recording.url, HTTP_RANGE="bytes=0-99")
        self.assertEqual(media.status_code, 206)
        self.assertEqual(len(media.content), 100)
        self.assertEqual(media["Content-Type"], "audio/webm")
        # Removed on request.
        self.client.post(reverse("genealogy:event_edit", args=[event.pk]), {
            "kind": "other", "title": "Bogʻdagi kun", "people": [self.p["me"].pk], "remove_recording": "on"})
        event.refresh_from_db()
        self.assertFalse(event.recording)

    def test_wrong_file_is_refused(self):
        response = self.client.post(reverse("genealogy:event_create"), {
            "kind": "other", "title": "X", "recording": SimpleUploadedFile("a.txt", b"hello", content_type="text/plain")})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.exists())

    def test_life_story_video(self):
        video = SimpleUploadedFile("m.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 500, content_type="video/mp4")
        self.client.post(reverse("genealogy:person_story", args=[self.p["me"].pk]),
                         {"life_story": "Bolaligim", "recording": video})
        item = Media.objects.get()
        self.assertTrue(item.in_story)
        self.assertEqual(item.kind, "video")
        self.assertContains(self.client.get(self.p["me"].get_absolute_url()), "<video")

    def test_recordings_are_private(self):
        self.client.post(reverse("genealogy:event_create"), {
            "kind": "other", "title": "Kun", "recording": self._voice()})
        url = Event.objects.get().recording.url
        stranger = account("begona", "Begona")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(url).status_code, 404)


def _answer(text="", calls=()):
    response = mock.Mock(status_code=200)
    parts = ([{"text": text}] if text else []) + [{"functionCall": c} for c in calls]
    response.json.return_value = {"candidates": [{"content": {"parts": parts}}]}
    return response


@override_settings(GEMINI_API_KEY="test-key")
class AssistantTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def ask(self, text, **kw):
        return self.client.post(reverse("assistant:message"), json.dumps({"message": text, "history": kw.get("history", [])}),
                                content_type="application/json")

    def test_page(self):
        self.assertContains(self.client.get(reverse("assistant:chat")), "data-ai")

    @override_settings(GEMINI_API_KEY="")
    def test_not_set_up(self):
        self.assertContains(self.client.get(reverse("assistant:chat")), "empty")
        self.assertEqual(self.ask("salom").status_code, 400)

    def test_answer_knows_the_family(self):
        with mock.patch("apps.assistant.gemini.requests.post", return_value=_answer("Bobongiz — Karim.")) as post:
            data = self.ask("Bobom kim?", history=[{"role": "model", "text": "skip"}, {"role": "user", "text": "Salom"},
                                                    {"role": "model", "text": "Salom!"}]).json()
        self.assertEqual(data["reply"], "Bobongiz — Karim.")
        body = post.call_args.kwargs["json"]
        self.assertIn("Karim", body["systemInstruction"]["parts"][0]["text"])
        self.assertIn("THIS IS THE USER", body["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(body["contents"][0]["role"], "user")  # a leading model turn is dropped
        self.assertEqual(body["contents"][-1]["parts"][0]["text"], "Bobom kim?")
        self.assertIn("tools", body)

    def test_story_is_saved_only_after_confirmation(self):
        call = {"name": "add_event", "args": {"kind": "other", "title": "Pushkin bogʻi", "story": "Bir kuni…",
                                              "people_ids": [self.p["me"].pk], "year": 2012}}
        with mock.patch("apps.assistant.gemini.requests.post", return_value=_answer("Qoʻshaymi?", [call])):
            data = self.ask("Bir hikoyam bor").json()
        self.assertEqual(len(data["proposals"]), 1)
        self.assertFalse(Event.objects.exists())
        saved = self.client.post(reverse("assistant:apply"), json.dumps({"token": data["proposals"][0]["token"]}),
                                 content_type="application/json").json()
        self.assertTrue(saved["ok"])
        event = Event.objects.get()
        self.assertEqual(event.title, "Pushkin bogʻi")
        self.assertEqual(list(event.people.all()), [self.p["me"]])

    def test_add_relative_follows_the_rules(self):
        call = {"name": "add_relative", "args": {"anchor_id": self.p["me"].pk, "relation": "father",
                                                 "first_name": "Boshqa", "gender": "male"}}
        with mock.patch("apps.assistant.gemini.requests.post", return_value=_answer("", [call])):
            token = self.ask("Otam Boshqa").json()["proposals"][0]["token"]
        response = self.client.post(reverse("assistant:apply"), json.dumps({"token": token}), content_type="application/json")
        self.assertEqual(response.status_code, 400)  # already has a father
        self.assertFalse(Person.objects.filter(first_name="Boshqa").exists())

    def test_tampered_or_foreign_token(self):
        response = self.client.post(reverse("assistant:apply"), json.dumps({"token": "abc"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        call = {"name": "update_person", "args": {"person_id": self.p["me"].pk, "occupation": "Dasturchi"}}
        with mock.patch("apps.assistant.gemini.requests.post", return_value=_answer("", [call])):
            token = self.ask("Men dasturchiman").json()["proposals"][0]["token"]
        stranger = account("begona", "Begona")
        self.client.force_login(stranger)
        response = self.client.post(reverse("assistant:apply"), json.dumps({"token": token}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.user)
        self.client.post(reverse("assistant:apply"), json.dumps({"token": token}), content_type="application/json")
        self.p["me"].refresh_from_db()
        self.assertEqual(self.p["me"].occupation, "Dasturchi")

    def test_busy_and_rate_limit(self):
        with mock.patch("apps.assistant.gemini.requests.post", return_value=mock.Mock(status_code=429)):
            self.assertEqual(self.ask("salom").status_code, 502)
        from django.core.cache import cache

        cache.set(f"assistant:{self.user.pk}", 999, 60)
        self.assertEqual(self.ask("salom").status_code, 429)
        cache.delete(f"assistant:{self.user.pk}")

    def test_transcribe(self):
        with mock.patch("apps.assistant.gemini.requests.post", return_value=_answer("Bir kuni bogʻda edik.")) as post:
            data = self.client.post(reverse("assistant:transcribe"),
                                    {"file": SimpleUploadedFile("v.weba", VOICE, content_type="audio/webm")}).json()
        self.assertEqual(data["text"], "Bir kuni bogʻda edik.")
        part = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["inlineData"]
        self.assertEqual(part["mimeType"], "video/webm")
