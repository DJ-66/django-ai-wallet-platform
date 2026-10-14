"""Process one AutoPost reservation without publishing."""

from auctions.ai_services.autopost_pipeline import (
    generate_autopost_draft,
)
from auctions.ai_services.autopost_processing import (
    claim_autopost,
    complete_autopost,
    fail_autopost,
    verify_autopost_claim,
)
from auctions.models import AutoPostPublication


def process_next_autopost(
    *,
    hashtags,
    vision_provider=None,
    localization_provider=None,
):
    """Claim, generate, validate and persist one AutoPost draft."""
    claimed = claim_autopost()

    if claimed is None:
        return {"status": "none"}

    publication_id, token = claimed

    try:
        publication = (
            AutoPostPublication.objects
            .select_related("media_asset", "configuration")
            .get(pk=publication_id)
        )

        if not verify_autopost_claim(publication_id, token):
            return {"status": "stale", "publication_id": publication_id}

        with publication.media_asset.image.open("rb") as image:
            image_bytes = image.read()

        translations = generate_autopost_draft(
            reservation=publication,
            image_bytes=image_bytes,
            hashtags=hashtags,
            vision_provider=vision_provider,
            localization_provider=localization_provider,
        )

        completed = complete_autopost(
            publication_id,
            token,
            translations,
            hashtags,
        )

        return {
            "status": "ready" if completed else "stale",
            "publication_id": publication_id,
        }

    except Exception as exc:
        failed = fail_autopost(publication_id, token, exc)
        return {
            "status": "failed" if failed else "stale",
            "publication_id": publication_id,
            "error": str(exc)[:500],
        }
