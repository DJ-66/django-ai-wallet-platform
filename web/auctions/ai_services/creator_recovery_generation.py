"""
Shared image-aware caption generation for creator recovery.

This service generates validated EN/ES/PT copy.
It does not modify database records or claim publications.
"""

from types import SimpleNamespace

from django.core.management.base import CommandError

from auctions.ai_services.creator_copy import (
    CreatorCopyError,
    generate_creator_post_copy,
)
from auctions.post_localization import (
    LocalizationOllamaProvider,
    PostLocalizationError,
    _translate_target,
)


def generate_recovery_translations(
    *,
    image_path,
    creator,
):
    hashtag_pool = creator["post_style"]["hashtags"]

    identity_tag = next(
        (
            tag
            for preferred in ("AIInfluencer", "DigitalCreator")
            for tag in hashtag_pool
            if tag.lower() == preferred.lower()
        ),
        hashtag_pool[0],
    )

    approved = [
        tag
        for tag in hashtag_pool
        if tag.lower() != identity_tag.lower()
    ]

    generated = None
    for attempt in range(1, 4):
        try:
            generated = generate_creator_post_copy(
                image_path=image_path,
                account=creator["account"],
                bio=creator.get("bio", ""),
                approved_hashtags=approved,
            )
            break
        except CreatorCopyError as exc:
            if (
                "Unapproved generated hashtag:" not in str(exc)
                or attempt == 3
            ):
                raise

    assert generated is not None

    if len(generated["hashtags"]) != 4:
        raise CommandError(
            "Creator AI must return four hashtags."
        )

    hashtags = (
        generated["hashtags"]
        + [identity_tag, "FANZ"]
    )

    english = {
        "title": generated["title"],
        "content": (
            generated["caption"]
            + "\n\n"
            + " ".join(f"#{tag}" for tag in hashtags)
        ),
    }

    sample = SimpleNamespace(**english)
    provider = LocalizationOllamaProvider()

    from auctions.management.commands.repair_creator_captions import (
        validate_recovery_translations,
    )

    translations = {"en": english}

    for language in ("es", "pt"):
        last_error = None

        for attempt in range(1, 4):
            try:
                candidate = _translate_target(
                    sample,
                    source_language="en",
                    target_language=language,
                    provider=provider,
                    attempts=1,
                )

                validate_recovery_translations(
                    {
                        "en": english,
                        "es": candidate if language == "es" else english,
                        "pt": candidate if language == "pt" else english,
                    },
                    hashtags,
                )

                translations[language] = candidate
                break

            except (CommandError, PostLocalizationError) as exc:
                last_error = exc

        else:
            raise CommandError(
                f"{language} recovery formatting failed "
                f"after 3 attempts: {last_error}"
            )

    validate_recovery_translations(
        translations,
        hashtags,
    )

    return translations, hashtags
