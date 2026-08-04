#!/usr/bin/env bash

set -euo pipefail

TEMPLATE_ROOT="${1:-web/templates}"

echo
echo "=== HTML templates with no translation tags ==="
find "$TEMPLATE_ROOT" -type f -name "*.html" \
    ! -exec grep -qE '\{%\s*(trans|blocktrans)\b' {} \; \
    -print

echo
echo "=== Likely hardcoded visible text ==="
grep -RniE \
    '>[[:space:]]*[A-Za-z][^<{]*<' \
    "$TEMPLATE_ROOT" \
    --include="*.html" || true

echo
echo "=== Likely hardcoded user-facing attributes ==="
grep -RniE \
    '(placeholder|title|aria-label|alt|value)="[^"]*[A-Za-z][^"]*"' \
    "$TEMPLATE_ROOT" \
    --include="*.html" || true

echo
echo "=== Templates using trans tags without loading i18n ==="
while IFS= read -r file; do
    if ! grep -qE '\{%\s*load[^%]*\bi18n\b' "$file"; then
        echo "$file"
    fi
done < <(
    grep -RlE \
        '\{%\s*(trans|blocktrans)\b' \
        "$TEMPLATE_ROOT" \
        --include="*.html" || true
)
