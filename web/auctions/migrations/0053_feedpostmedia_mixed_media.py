from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0052_feedpostmedia"),
    ]

    operations = [
        migrations.RenameField(
            model_name="feedpostmedia",
            old_name="image",
            new_name="file",
        ),
        migrations.AlterField(
            model_name="feedpostmedia",
            name="file",
            field=models.FileField(
                upload_to="feed/media/",
            ),
        ),
        migrations.AddField(
            model_name="feedpostmedia",
            name="media_type",
            field=models.CharField(
                choices=[
                    ("image", "Image"),
                    ("video", "Video"),
                    ("audio", "Audio"),
                    ("pdf", "PDF"),
                ],
                db_index=True,
                default="image",
                max_length=20,
            ),
        ),
    ]
