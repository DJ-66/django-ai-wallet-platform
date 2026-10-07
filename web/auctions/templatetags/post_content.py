import re
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import bleach
import markdown

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe


register = template.Library()


MENTION_RE = re.compile(
    r"(?<![\w@])@([A-Za-z0-9_]{1,150})"
)

HASHTAG_RE = re.compile(
    r"(?<![\w#])#([\w]{2,50})"
)


ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "code",
    "pre",
    "a",
]

ALLOWED_ATTRS = {
    "a": [
        "href",
        "title",
    ],
}


def _link_text(text):
    """
    Link FANZ @mentions and #hashtags in one plain-text node.

    Link candidates are detected in the original plain text.
    All non-link text is escaped while assembling the result,
    so HTML entities introduced by escaping cannot become
    synthetic hashtags or mentions.
    """
    matches = []

    for match in MENTION_RE.finditer(text):
        matches.append(
            (
                match.start(),
                match.end(),
                "mention",
                match,
            )
        )

    for match in HASHTAG_RE.finditer(text):
        matches.append(
            (
                match.start(),
                match.end(),
                "hashtag",
                match,
            )
        )

    matches.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    parts = []
    cursor = 0

    for start, end, kind, match in matches:
        if start < cursor:
            continue

        parts.append(
            str(
                escape(
                    text[cursor:start]
                )
            )
        )

        value = match.group(1)

        if kind == "mention":
            href = reverse(
                "public_profile_root",
                kwargs={
                    "username": value,
                },
            )

            parts.append(
                f'<a href="{href}" '
                f'class="fanz-mention">'
                f'@{escape(value)}</a>'
            )
        else:
            href = reverse(
                "hashtag_feed",
                kwargs={
                    "tag_name":
                        value.lower(),
                },
            )

            parts.append(
                f'<a href="{href}" '
                f'class="hashtag-link">'
                f'#{escape(value)}</a>'
            )

        cursor = end

    parts.append(
        str(
            escape(
                text[cursor:]
            )
        )
    )

    return "".join(parts)


class _FanzTextLinkifier(HTMLParser):
    """
    Link FANZ mentions and hashtags only in text nodes.

    Existing anchors, code blocks, and preformatted blocks are
    deliberately left alone.
    """

    SKIP_TAGS = {
        "a",
        "code",
        "pre",
    }

    VOID_TAGS = {
        "br",
    }

    def __init__(self):
        super().__init__(
            convert_charrefs=False,
        )

        self.parts = []
        self.skip_depth = 0

    def _attrs_html(self, attrs):
        rendered = []

        for name, value in attrs:
            if value is None:
                rendered.append(
                    f" {name}"
                )
                continue

            rendered.append(
                f' {name}="'
                f'{html_escape(value, quote=True)}'
                f'"'
            )

        return "".join(rendered)

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

        attrs_html = self._attrs_html(
            attrs
        )

        if tag in self.VOID_TAGS:
            self.parts.append(
                f"<{tag}{attrs_html}>"
            )
        else:
            self.parts.append(
                f"<{tag}{attrs_html}>"
            )

    def handle_startendtag(
        self,
        tag,
        attrs,
    ):
        attrs_html = self._attrs_html(
            attrs
        )

        self.parts.append(
            f"<{tag}{attrs_html}>"
        )

    def handle_endtag(
        self,
        tag,
    ):
        self.parts.append(
            f"</{tag}>"
        )

        if (
            tag in self.SKIP_TAGS
            and self.skip_depth > 0
        ):
            self.skip_depth -= 1

    def handle_data(
        self,
        data,
    ):
        if self.skip_depth:
            self.parts.append(
                escape(data)
            )
            return

        self.parts.append(
            _link_text(data)
        )

    def handle_entityref(
        self,
        name,
    ):
        self.parts.append(
            f"&{name};"
        )

    def handle_charref(
        self,
        name,
    ):
        self.parts.append(
            f"&#{name};"
        )

    def get_html(self):
        return "".join(
            self.parts
        )


def _link_fanz_text_nodes(html):
    parser = _FanzTextLinkifier()
    parser.feed(html)
    parser.close()

    return parser.get_html()


def _set_link_policy(
    attrs,
    new=False,
):
    """
    Internal FANZ links stay in the same tab.

    External HTTPS links open in a new tab and receive safe rel
    attributes.

    Unsupported destinations fail closed.
    """
    href_key = (
        None,
        "href",
    )

    href = attrs.get(
        href_key,
        "",
    ).strip()

    if not href:
        return attrs

    parsed = urlsplit(
        href
    )

    is_internal = (
        href.startswith("/")
        and not href.startswith("//")
    )

    is_external_https = (
        parsed.scheme.lower()
        == "https"
        and bool(parsed.netloc)
    )

    if is_internal:
        attrs.pop(
            (None, "target"),
            None,
        )

        attrs.pop(
            (None, "rel"),
            None,
        )

        return attrs

    if is_external_https:
        attrs[
            (None, "target")
        ] = "_blank"

        attrs[
            (None, "rel")
        ] = (
            "noopener noreferrer ugc"
        )

        return attrs

    attrs.pop(
        href_key,
        None,
    )

    attrs.pop(
        (None, "target"),
        None,
    )

    attrs.pop(
        (None, "rel"),
        None,
    )

    return attrs


@register.filter
def render_post_content(value):
    if not value:
        return ""

    source = str(value)

    # 1. Interpret Markdown and explicitly supplied HTML.
    html = markdown.markdown(
        source,
        extensions=[
            "extra",
            "nl2br",
        ],
    )

    # 2. Sanitize user-controlled markup before doing anything
    #    that will become trusted HTML.
    cleaner = bleach.Cleaner(
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols={
            "https",
        },
        strip=True,
    )

    clean = cleaner.clean(
        html
    )

    # 3. Add FANZ-native links only to ordinary text nodes.
    clean = _link_fanz_text_nodes(
        clean
    )

    # 4. Apply external/internal link behavior and auto-link
    #    ordinary HTTPS URLs.
    clean = bleach.linkifier.Linker(
        callbacks=[
            _set_link_policy,
        ],
        skip_tags=[
            "pre",
            "code",
        ],
        parse_email=False,
    ).linkify(
        clean
    )

    return mark_safe(
        clean
    )


TRAILING_HASHTAG_LINE_RE = re.compile(
    r"^\s*(?:#[\w]{2,50}\s*)+$"
)


def _split_trailing_hashtag_block(value):
    """
    Split a trailing hashtag-only block from post content.

    Storage remains unchanged. This is presentation-only so media
    can render between the post body and its trailing hashtag row.
    Hashtags used naturally inside ordinary prose remain in the body.
    """
    source = str(value or "")

    if not source:
        return "", ""

    lines = source.splitlines()
    hashtag_lines = []

    while lines:
        candidate = lines[-1]

        if not candidate.strip():
            if hashtag_lines:
                lines.pop()
                continue
            break

        if not TRAILING_HASHTAG_LINE_RE.fullmatch(candidate):
            break

        hashtag_lines.insert(
            0,
            lines.pop(),
        )

    body = "\n".join(lines).rstrip()
    hashtags = "\n".join(hashtag_lines).strip()

    return body, hashtags


@register.filter
def post_body(value):
    body, _hashtags = _split_trailing_hashtag_block(
        value
    )
    return body


@register.filter
def post_trailing_hashtags(value):
    _body, hashtags = _split_trailing_hashtag_block(
        value
    )
    return hashtags
