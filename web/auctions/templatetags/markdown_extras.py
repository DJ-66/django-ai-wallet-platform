import markdown
import bleach

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "ul", "ol", "li",
    "h1", "h2", "h3", "blockquote", "code", "pre",
    "a"
]

ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
}

@register.filter
def markdownify(value):
    if not value:
        return ""

    html = markdown.markdown(
        value,
        extensions=["extra", "nl2br"]
    )

    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True
    )

    return mark_safe(clean)
