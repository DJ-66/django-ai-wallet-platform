from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0120_merge_phase14_publishing_autopost"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="feedpost",
            options={
                "ordering": ["-created_at"],
                "default_manager_name": "objects",
                "base_manager_name": "all_objects",
            },
        ),
        migrations.AlterModelManagers(
            name="feedpost",
            managers=[
                ("objects", models.Manager()),
                ("all_objects", models.Manager()),
            ],
        ),
        migrations.AddField(
            model_name="feedpost",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
    ]
