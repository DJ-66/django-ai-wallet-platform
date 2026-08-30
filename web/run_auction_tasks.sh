#!/bin/sh

REMINDER_COUNTER=0
PAYMENT_COUNTER=0

while true
do
    python manage.py process_auctions

    REMINDER_COUNTER=$((REMINDER_COUNTER + 1))
    PAYMENT_COUNTER=$((PAYMENT_COUNTER + 1))

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

        PAYMENT_COUNTER=0
    fi

    # Run reminders every 10 minutes if loop sleeps 10 seconds
    if [ "$REMINDER_COUNTER" -ge 60 ]; then
        python manage.py send_auction_reminders
        REMINDER_COUNTER=0
    fi

    sleep 10
done
