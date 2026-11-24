"""Select creator hashtags without mandatory generic identity tags."""

import random
import re


def split_creator_hashtag_pool(hashtags, *, rng=None):
    """Return one rotating tag and the remaining AI-approved candidates."""

    if not isinstance(hashtags, (list, tuple)):
        raise ValueError("Expected a creator hashtag list.")

    pool = []
    seen = set()

    for tag in hashtags:
        if (
            not isinstance(tag, str)
            or re.fullmatch(r"[A-Za-z0-9_]+", tag) is None
        ):
            raise ValueError("Invalid creator hashtag.")

        key = tag.lower()

        if key == "fanz":
            continue

        if key in seen:
            raise ValueError("Duplicate creator hashtag.")

        seen.add(key)
        pool.append(tag)

    if len(pool) < 5:
        raise ValueError("At least five creator hashtags are required.")

    rng = rng if rng is not None else random.SystemRandom()

    rotating_tag = rng.choice(pool)

    approved = [
        tag for tag in pool
        if tag.lower() != rotating_tag.lower()
    ]

    return rotating_tag, approved
