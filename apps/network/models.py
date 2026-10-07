"""Connections between accounts, and the same person found in two family trees.

A *connection* starts as a request from one account to another: "you are my
cousin" (and here you are in my tree), or "let us be friends". When it is
accepted, each of them is placed in the other's tree, the trees can be
opened by both, and the friends appear in each other's list of friends.

A *match* says that two records in two different family trees are one and
the same person ("this is the same person"). Matches let a family tree take
over the relatives that another tree already knows.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import pgettext_lazy


class Connection(models.Model):
    class Kind(models.TextChoices):
        RELATIVE = "relative", pgettext_lazy("connection", "Relative")
        FRIEND = "friend", pgettext_lazy("connection", "Friend")

    class Status(models.TextChoices):
        PENDING = "pending", pgettext_lazy("connection", "Waiting for an answer")
        ACCEPTED = "accepted", pgettext_lazy("connection", "Connected")
        DECLINED = "declined", pgettext_lazy("connection", "Declined")

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connections_sent")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="connections_received")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.RELATIVE)
    # The family tree each of them works in for this connection (their own, or
    # a shared one they may edit).
    sender_tree = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    recipient_tree = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="+")
    # Where the recipient stands in the sender's tree: a record that is
    # already there, or a new one added as `sender_relation` of `sender_anchor`
    # once the request is accepted.
    sender_person = models.ForeignKey("genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    sender_relation = models.CharField(max_length=10, blank=True)
    sender_anchor = models.ForeignKey("genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    # Where the sender stands in the recipient's tree (chosen when accepting).
    recipient_person = models.ForeignKey("genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="+")
    share_trees = models.BooleanField(default=True)
    befriend = models.BooleanField(default=False)
    # Memberships this connection created: ending it removes exactly these.
    shared_memberships = models.JSONField(default=list, blank=True)
    message = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "status"]), models.Index(fields=["sender", "status"])]

    def __str__(self):
        return f"{self.sender} → {self.recipient} ({self.status})"

    def other(self, user):
        return self.recipient if user.pk == self.sender_id else self.sender

    def tree_of(self, user):
        return self.sender_tree if user.pk == self.sender_id else self.recipient_tree

    def person_for(self, user):
        """The record of the *other* account in `user`'s family tree."""
        return self.sender_person if user.pk == self.sender_id else self.recipient_person


class Follow(models.Model):
    """Following an account (Instagram-style). A private account approves each follower."""

    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_set")
    followed = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers_set")
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["follower", "followed"], name="unique_follow")]

    def __str__(self):
        return f"{self.follower} → {self.followed}{'' if self.approved else ' (requested)'}"


class PersonMatch(models.Model):
    """Two records of one person in two family trees (`first.pk < second.pk`)."""

    first = models.ForeignKey("genealogy.Person", on_delete=models.CASCADE, related_name="+")
    second = models.ForeignKey("genealogy.Person", on_delete=models.CASCADE, related_name="+")
    # "These are different people": the pair is not suggested again.
    rejected = models.BooleanField(default=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["first", "second"], name="unique_person_match")]

    def other(self, person_id):
        return self.second if person_id == self.first_id else self.first
