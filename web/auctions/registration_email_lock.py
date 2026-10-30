"""Serialize FANZ registrations by normalized email."""

from django.contrib.auth import get_user_model
from django.db import connection


class RegistrationEmailConflict(Exception):
    """The requested account email is already registered."""


def lock_registration_email(email):
    """
    Acquire a PostgreSQL transaction-scoped email lock.

    Must be called inside transaction.atomic(), before
    creating any account or wallet records.
    """
    normalized = str(email).strip().lower()

    if not normalized:
        raise ValueError("Registration email is required.")

    if connection.vendor != "postgresql":
        raise RuntimeError(
            "Email registration locking requires PostgreSQL."
        )

    if not connection.in_atomic_block:
        raise RuntimeError(
            "Email registration lock requires transaction.atomic()."
        )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(%s, 0))",
            [normalized],
        )

    User = get_user_model()

    if User.objects.filter(
        email__iexact=normalized
    ).exists():
        raise RegistrationEmailConflict()

    return normalized
