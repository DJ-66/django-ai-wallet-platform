"""Shared public event visibility rules for FANZ."""

from django.db.models import Q
from django.utils import timezone


def public_event_visibility_q(now=None):
    """
    An event remains visible until its end time.

    If no end time exists, visibility ends at its start time.
    """
    if now is None:
        now = timezone.now()

    return (
        Q(is_published=True)
        & Q(is_cancelled=False)
        & (
            Q(end_at__gt=now)
            | Q(
                end_at__isnull=True,
                start_at__gt=now,
            )
        )
    )
