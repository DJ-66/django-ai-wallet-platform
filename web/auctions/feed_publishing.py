from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import FeedPostForm
from .hashtags import sync_post_hashtags
from .models import FeedPostMedia


def publish_feed_post(
    *,
    user,
    title="",
    content="",
    uploads=None,
    is_public=True,
    is_paid=False,
    unlock_price=0,
):
    """
    Publish a FANZ feed post through the same validation and media
    processing path used by the interactive feed form.

    uploads must be a list of Django UploadedFile objects.
    Images are normalized through FeedPostForm, including FANZ WebP
    conversion and creator-specific footer branding.
    """
    uploads = list(uploads or [])

    form = FeedPostForm(
        data={
            "title": title or "",
            "content": content or "",
            "media_type": FeedPostMedia.MEDIA_TYPE_IMAGE,
            "is_public": bool(is_public),
            "is_paid": bool(is_paid),
            "unlock_price": unlock_price or 0,
        },
        files={
            "images": uploads,
        },
        current_username=user.username,
    )

    if not form.is_valid():
        raise ValidationError(form.errors.get_json_data())

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

        media_items = form.cleaned_data.get("images", [])

        for display_order, media_item in enumerate(media_items):
            FeedPostMedia.objects.create(
                post=post,
                file=media_item["file"],
                media_type=media_item["media_type"],
                caption="",
                display_order=display_order,
                is_active=True,
            )

        sync_post_hashtags(post)

    return post
