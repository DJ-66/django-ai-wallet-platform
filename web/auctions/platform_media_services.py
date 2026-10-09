from django.db import IntegrityError, transaction

from auctions.models import PlatformMediaAsset


def save_platform_media(account, items):
    """
    Save validated reusable images for one account.

    Duplicate uploads are skipped. Files created by failed
    database inserts are cleaned up.
    """
    created = 0
    duplicates = 0

    for item in items:
        digest = item["sha256"]

        if PlatformMediaAsset.objects.filter(
            account=account,
            sha256=digest,
        ).exists():
            duplicates += 1
            continue

        last_order = (
            PlatformMediaAsset.objects
            .filter(account=account)
            .order_by("-display_order", "-pk")
            .values_list("display_order", flat=True)
            .first()
        )

        asset = PlatformMediaAsset(
            account=account,
            sha256=digest,
            display_order=(
                0 if last_order is None
                else last_order + 1
            ),
            is_active=True,
        )

        saved_name = None

        try:
            with transaction.atomic():
                asset.image.save(
                    item["file"].name,
                    item["file"],
                    save=False,
                )

                saved_name = asset.image.name
                asset.save()

        except IntegrityError:
            if saved_name:
                asset.image.storage.delete(saved_name)

            duplicates += 1
            continue

        except Exception:
            if saved_name:
                asset.image.storage.delete(saved_name)
            raise

        created += 1

    return created, duplicates
