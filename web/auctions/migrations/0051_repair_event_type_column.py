from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0050_alter_userprofile_is_ai_influencer"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE auctions_event
                ADD COLUMN IF NOT EXISTS event_type
                varchar(20) NOT NULL DEFAULT 'general';
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE auctions_event
                ALTER COLUMN event_type DROP DEFAULT;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
