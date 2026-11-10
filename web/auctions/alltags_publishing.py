"""Interactive FANZ publishing with optional #allTags promotion."""

from django.db import transaction

from .alltags_services import (
    AllTagsPromotionDenied,
    purchase_alltags_promotion,
)
from .hashtags import sync_post_hashtags
from .models import FeedPostMedia


SUCCESS = "Promotion Successful ! (You Paid 20 Credits)"


def publish_interactive_post(*, form, user, alltags=False, on_media_saved=None):
    """
    Publish an already-validated form.

    Expected promotion denials preserve the ordinary post.
    Unexpected failures roll back database changes.
    """
    if not form.is_valid():
        raise ValueError("Publishing requires a valid form.")

    saved_files = []

    try:
        with transaction.atomic():
            post = form.save(commit=False)
            post.user = user
            post.title = post.title.strip()
            post.content = post.content.strip()

            if post.is_paid:
                post.is_public = False
                if post.unlock_price < 1:
                    post.unlock_price = 1
            else:
                post.unlock_price = 0

            post.save()

            for order, item in enumerate(
                form.cleaned_data.get("images", [])
            ):
                media = FeedPostMedia(
                    post=post,
                    file=item["file"],
                    media_type=item["media_type"],
                    caption="",
                    display_order=order,
                    is_active=True,
                )

                media.file.save(
                    item["file"].name,
                    item["file"],
                    save=False,
                )

                saved_files.append(
                    (media.file.storage, media.file.name)
                )

                if on_media_saved is not None:
                    on_media_saved(
                        media.file.storage,
                        media.file.name,
                    )

                media.save()

            sync_post_hashtags(post)

            outcome = None

            if alltags:
                try:
                    with transaction.atomic():
                        purchase_alltags_promotion(
                            creator=user,
                            post=post,
                        )
                except AllTagsPromotionDenied as exc:
                    outcome = str(exc.messages[0])
                else:
                    outcome = SUCCESS

            return post, outcome

    except Exception:
        for storage, name in reversed(saved_files):
            try:
                storage.delete(name)
            except Exception:
                pass
        raise
