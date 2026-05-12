#!/bin/sh

#!/bin/sh

REMINDER_COUNTER=0

while true
do
    python manage.py process_auctions

    REMINDER_COUNTER=$((REMINDER_COUNTER + 1))

    # Run reminders every 10 minutes if loop sleeps 10 seconds
    if [ "$REMINDER_COUNTER" -ge 60 ]; then
        python manage.py send_auction_reminders
        REMINDER_COUNTER=0
    fi

    sleep 10
done

