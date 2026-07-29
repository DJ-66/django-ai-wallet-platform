from django.db import migrations


def migrate_legacy_auction_media(apps, schema_editor):
    Auction = apps.get_model("auctions", "Auction")
    AuctionMedia = apps.get_model("auctions", "AuctionMedia")

    for auction in Auction.objects.all().iterator():
        # Auction Studio is already the source of truth for this auction.
        # Skipping the entire auction prevents stale legacy fields from
        # being imported alongside newer AuctionMedia records.
        if AuctionMedia.objects.filter(auction_id=auction.pk).exists():
            continue

        media_records = []

        image_name = getattr(auction.image, "name", "") or ""

        if image_name:
            media_records.append(
                AuctionMedia(
                    auction_id=auction.pk,
                    file=image_name,
                    media_type="image",
                    display_order=0,
                    is_active=True,
                )
            )

        image_2_name = getattr(auction.image_2, "name", "") or ""

        if image_2_name:
            media_records.append(
                AuctionMedia(
                    auction_id=auction.pk,
                    file=image_2_name,
                    media_type="image",
                    display_order=1,
                    is_active=True,
                )
            )

        video_name = getattr(auction.video, "name", "") or ""

        if video_name:
            media_records.append(
                AuctionMedia(
                    auction_id=auction.pk,
                    file=video_name,
                    media_type="video",
                    display_order=0,
                    is_active=True,
                )
            )

        if media_records:
            AuctionMedia.objects.bulk_create(media_records)


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0054_auctionmedia"),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_auction_media,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
