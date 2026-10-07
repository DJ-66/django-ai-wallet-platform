#!/bin/sh

REMINDER_COUNTER=0
PAYMENT_COUNTER=0
LOCALIZATION_COUNTER=0

while true
do
    python manage.py process_auctions

    # Publish at most one due AI creator feed post per loop.
    # ScheduledPublication row locking makes concurrent claims safe.
    python manage.py process_scheduled_publications

    REMINDER_COUNTER=$((REMINDER_COUNTER + 1))
    PAYMENT_COUNTER=$((PAYMENT_COUNTER + 1))
    LOCALIZATION_COUNTER=$((LOCALIZATION_COUNTER + 1))

    # Fulfill settled payments approximately once per minute.
    if [ "$PAYMENT_COUNTER" -ge 6 ]; then
        python manage.py fulfill_settled_payments

        # Prepare any newly-created economy asset delivery obligations.
        # External chain submission is handled separately; this currently
        # advances only pending -> prepared through the private adapter.
        python manage.py process_pending_economy_deliveries

        # Advance at most one prepared Founder creator-coin
        # publication per minute. The Sui service remains
        # authoritative for PREPARE/SUBMIT safety gates.
        python manage.py process_next_founder_coin_publication

        # Check whether a SunsetCam daily capture slot is due.
        # The command is idempotent through SunsetCamCapture.
        python manage.py process_sunsetcam_capture

        # Maintain one pending publication per AI creator.
        # The generator is idempotent while a creator already has
        # queued or publishing work.
        python manage.py generate_ai_publications

        PAYMENT_COUNTER=0
    fi

    # Run reminders every 10 minutes if loop sleeps 10 seconds.
    if [ "$REMINDER_COUNTER" -ge 60 ]; then
        python manage.py send_auction_reminders
        REMINDER_COUNTER=0
    fi

    # Audit at most 10 public posts approximately every 30 minutes.
    # Complete EN/ES/PT posts make no localization AI call; stale
    # source-copy rows are repaired conservatively.
    # Newest posts are processed first so fresh content does not
    # wait behind the historical localization backlog.
    if [ "$LOCALIZATION_COUNTER" -ge 180 ]; then
        python manage.py localize_feed_posts --limit 10
        LOCALIZATION_COUNTER=0
    fi

    sleep 10
done
