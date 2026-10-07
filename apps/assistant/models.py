from django.conf import settings
from django.db import models


class Note(models.Model):
    """A message one family member leaves with the assistant for another: greetings, a word, a joke.

    The assistant passes it on, word for word, the next time the recipient talks to it."""

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_notes")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} → {self.recipient}"
