"""Prepare complete English captions for FANZ AI publications."""

from auctions.ai_services.legacy_gemma_closer import (
    generate_gemma_dm_closer,
)
from auctions.ai_services.cta_links import creator_dm_link
from auctions.ai_services.legacy_suffix_assembly import (
    decorate_v2_creator_caption,
    decorate_creator_caption,
)
from auctions.ai_services.legacy_publication_preparation import (
    plan_v2_publication_ending,
    plan_publication_ending,
)



def prepare_v2_ai_caption(
    *,
    username,
    bio,
    publication_key,
    sequence,
    content,
    recent_closers=(),
):
    """Return one prepared caption and its ending plan."""

    plan = plan_v2_publication_ending(
        username=username,
        publication_key=publication_key,
        sequence=sequence,
    )

    if plan.kind == "creative":
        closer = generate_gemma_dm_closer(
            username=username,
            bio=bio,
            personality=plan.personality,
            caption=content.split("\n\n", 1)[0],
            recent_closers=recent_closers,
        )

        caption, separator, hashtags = content.rpartition("\n\n")

        if not separator or not caption.strip() or not hashtags.strip():
            raise ValueError("Invalid creator caption format")

        if any(line.strip() == closer for line in caption.splitlines()):
            raise ValueError("Creative closer already applied")

        prepared = (
            caption.rstrip()
            + "\n\n"
            + "↳ 💋❤️😘 "
            + closer
            + " XOXO 💕"
            + "\n\n"
            + creator_dm_link(username)
            + "\n\n"
            + hashtags
        )

    else:
        prepared = decorate_v2_creator_caption(
            content=content,
            language="en",
            suffix=plan.suffix,
            destination=plan.destination,
        )

    if len(prepared) > 2000:
        raise ValueError("Prepared scheduled caption exceeds 2000 characters")

    return prepared, plan

def prepare_ai_caption(
    *,
    username,
    bio,
    publication_key,
    sequence,
    content,
    recent_closers=(),
):
    """Return one prepared caption and its ending plan."""

    plan = plan_publication_ending(
        username=username,
        publication_key=publication_key,
        sequence=sequence,
    )

    if plan.kind == "creative":
        closer = generate_gemma_dm_closer(
            username=username,
            bio=bio,
            personality=plan.personality,
            caption=content.split("\n\n", 1)[0],
            recent_closers=recent_closers,
        )

        caption, separator, hashtags = content.rpartition("\n\n")

        if not separator or not caption.strip() or not hashtags.strip():
            raise ValueError("Invalid creator caption format")

        if any(line.strip() == closer for line in caption.splitlines()):
            raise ValueError("Creative closer already applied")

        prepared = caption + "\n" + closer + "\n\n" + hashtags

    else:
        prepared = decorate_creator_caption(
            content=content,
            language="en",
            suffix=plan.suffix,
            destination=plan.destination,
        )

    if len(prepared) > 2000:
        raise ValueError("Prepared scheduled caption exceeds 2000 characters")

    return prepared, plan
