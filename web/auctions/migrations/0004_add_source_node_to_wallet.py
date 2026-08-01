from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF to_regclass('public.auctions_bidwallet') IS NOT NULL THEN
        ALTER TABLE auctions_bidwallet
        ADD COLUMN IF NOT EXISTS source_node_id bigint NULL;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'auctions_bidwallet_source_node_id_fk'
        ) THEN
            ALTER TABLE auctions_bidwallet
            ADD CONSTRAINT auctions_bidwallet_source_node_id_fk
            FOREIGN KEY (source_node_id)
            REFERENCES auctions_nodeprofile(id)
            DEFERRABLE INITIALLY DEFERRED;
        END IF;

        CREATE INDEX IF NOT EXISTS
            auctions_bidwallet_source_node_id_idx
        ON auctions_bidwallet(source_node_id);
    END IF;
END
$$;
"""


REVERSE_SQL = """
DO $$
BEGIN
    IF to_regclass('public.auctions_bidwallet') IS NOT NULL THEN
        ALTER TABLE auctions_bidwallet
        DROP CONSTRAINT IF EXISTS
            auctions_bidwallet_source_node_id_fk;

        DROP INDEX IF EXISTS
            auctions_bidwallet_source_node_id_idx;

        ALTER TABLE auctions_bidwallet
        DROP COLUMN IF EXISTS source_node_id;
    END IF;
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("auctions", "0003_add_node_profile_only"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]
