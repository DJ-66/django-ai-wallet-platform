import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

HASHTAG_RE = re.compile(r"#([\w]{2,50})")


@register.filter
def link_hashtags(text):
    if not text:
        return ""

    escaped = escape(text)

    def repl(match):
        raw_tag = match.group(1)
        tag = raw_tag.lower()
        return f'<a href="/auctions/tag/{tag}/" class="hashtag-link">#{raw_tag}</a>'

    return mark_safe(HASHTAG_RE.sub(repl, escaped))
