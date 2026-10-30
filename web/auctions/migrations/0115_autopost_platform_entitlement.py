from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "auctions",
            "0114_autopost_subscription_transaction_type",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="autopostentitlement",
            name="source",
            field=models.CharField(
                max_length=12,
                choices=[
                    ("paid", "Paid subscription"),
                    ("pilot", "Authorized pilot"),
                    ("platform", "Platform-managed creator"),
                ],
            ),
        ),
        migrations.RemoveConstraint(
            model_name="autopostentitlement",
            name="autopost_entitlement_valid_source",
        ),
        migrations.AddConstraint(
            model_name="autopostentitlement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        source="paid",
                        payment_transaction__isnull=False,
                    )
                    | models.Q(
                        source__in=["pilot", "platform"],
                        payment_transaction__isnull=True,
                    )
                ),
                name="autopost_entitlement_valid_source",
            ),
        ),
    ]
