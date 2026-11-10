# Phase 14: merge crash-safe publishing and AutoPost histories.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0104_creator_publishing_attempt"),
        ("auctions", "0119_feedpostsubmission_request_fingerprint"),
    ]

    operations = []
