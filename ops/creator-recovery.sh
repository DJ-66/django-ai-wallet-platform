#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/home/dj/fanz-ops"
APP="/home/dj/stacks/django-monolith"
LOG="$ROOT/logs/creator-recovery.log"
LOCK="$ROOT/creator-recovery.lock"
LIMIT=5

mkdir -p "$ROOT/logs"

exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -Is) SKIPPED: another batch is running" >> "$LOG"
    exit 0
fi

cd "$APP"

tmp=$(mktemp)
active_container=""

cleanup() {
    if [[ -n "$active_container" ]]; then
        docker rm -f "$active_container" >/dev/null 2>&1 || true
    fi
    rm -f "$tmp"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

completed=0
start=$(date +%s)

echo "$(date -Is) BATCH START scope=published limit=$LIMIT" \
    | tee -a "$LOG"

for ((attempt=1; attempt<=LIMIT; attempt++)); do
    active_container="fanz-caption-recovery-$$-$attempt"
    : > "$tmp"

    attempt_started=$(date -u +%Y-%m-%dT%H:%M:%S%z)
    rc=0
    if docker compose run -d --no-deps \
        --name "$active_container" --entrypoint python \
        -e FANZ_LOCALIZATION_MODEL=gemma3:latest \
        web manage.py process_creator_caption_recovery \
        --scope published > "$tmp" 2>&1; then

        if wait_result=$(timeout 8m docker wait "$active_container"); then
            if [[ "$wait_result" =~ ^[0-9]+$ ]]; then
                rc=$wait_result
            else
                rc=125
            fi
        else
            rc=$?
        fi
    else
        rc=$?
    fi

    docker logs "$active_container" >> "$tmp" 2>&1 || true
    docker rm -f "$active_container" >/dev/null 2>&1 || true
    active_container=""
    cat "$tmp" | tee -a "$LOG"

    if (( rc != 0 )); then
        # Only application exit 1 can represent a recorded AI failure.
        if (( rc == 1 )); then
            id=$(sed -n 's/^creator_caption_recovery_failed=\([0-9][0-9]*\)$/\1/p' "$tmp")

            if [[ "$id" =~ ^[0-9]+$ ]] &&
               [[ $(grep -Ec '^creator_caption_recovery_failed=[0-9]+$' "$tmp") -eq 1 ]] &&
               grep -Eq '^(CommandError: (es|pt) recovery formatting failed|.*CreatorCopyError: Unapproved generated hashtag:)' "$tmp"; then

                error=$(sed -nE 's/^CommandError: ((es|pt) recovery formatting failed.*)$/\1/p; s/^.*CreatorCopyError: (.*Unapproved generated hashtag:.*)$/\1/p' "$tmp" | head -n 1)

                if [[ -n "$error" ]] &&
                   docker compose exec -T \
                    -e RECOVERY_PUBLICATION_ID="$id" \
                    -e RECOVERY_EXPECTED_ERROR="$error" \
                    web python manage.py shell -c '
import os
from django.utils import timezone
from auctions.models import CreatorCaptionRecoveryState

state = CreatorCaptionRecoveryState.objects.filter(
    publication_id=int(os.environ["RECOVERY_PUBLICATION_ID"]),
    status="failed",
    next_retry_at__gt=timezone.now(),
).first()

error = state.last_error.strip() if state else ""
expected = os.environ["RECOVERY_EXPECTED_ERROR"].strip()
print("RECORDED_AI_FAILURE=" + str(bool(
    error
    and error == expected
    and (
        error.startswith("es recovery formatting failed")
        or error.startswith("pt recovery formatting failed")
        or error.startswith("Unapproved generated hashtag:")
    )
)))
' > "$tmp.verify" 2>&1; then

                    if grep -qx 'RECORDED_AI_FAILURE=True' "$tmp.verify"; then
                        echo "$(date -Is) RECORDED AI FAILURE publication=$id; continuing" | tee -a "$LOG"
                        continue
                    fi
                fi
            fi
        fi

        echo "$(date -Is) FAILED attempt=$attempt exit=$rc" | tee -a "$LOG"
        exit 1
    fi

    if grep -qx 'creator_caption_recovery_due=none' "$tmp"; then
        echo "$(date -Is) NO ELIGIBLE PUBLICATIONS" \
            | tee -a "$LOG"
        break
    fi

    if [[ $(grep -Ec '^creator_caption_recovery_completed=[0-9]+$' "$tmp") -ne 1 ]]; then
        echo "$(date -Is) FAILED: unexpected command output" \
        exit 1
    fi

    id=$(sed -n 's/^creator_caption_recovery_completed=//p' "$tmp")

    ((completed+=1))

    echo "$(date -Is) SUCCESS publication=$id" \
        | tee -a "$LOG"
done

elapsed=$(( $(date +%s) - start ))

echo "$(date -Is) BATCH FINISHED completed=$completed elapsed=${elapsed}s" \
    | tee -a "$LOG"
