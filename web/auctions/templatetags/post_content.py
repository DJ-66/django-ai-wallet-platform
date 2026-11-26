import ipaddress
import re
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

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

BARE_FANZ_PATH_RE = re.compile(
    r"(?<!\S)/(?:autoPoster|BuyCredits)/(?![\w/])(?:\?[A-Za-z0-9_=&%./:-]*)?(?:\#[A-Za-z0-9_.-]*)?"
)


HASHTAG_RE = re.compile(
    r"(?<![\w#])#([\w]{2,50})"
)

WWW_TOKEN_RE = re.compile(
    r"(?<![\w@=/:])www\."
    r"(?![^\s<>\"']*@)[^\s<>\"'@]+",
    re.IGNORECASE,
)

HTTPS_TOKEN_RE = re.compile(
    r"(?<![\w@=/:])https://[^\s<>\"']+",
    re.IGNORECASE,
)

URL_TRAILING_PUNCTUATION = ".,!?;:"
URL_CLOSING_PAIRS = {
    ")": "(",
    "]": "[",
    "}": "{",
}


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


def _trim_url_candidate(candidate):
    url = candidate.rstrip(URL_TRAILING_PUNCTUATION)

    while url and url[-1] in URL_CLOSING_PAIRS:
        closing = url[-1]
        opening = URL_CLOSING_PAIRS[closing]

        if url.count(closing) <= url.count(opening):
            break

        url = url[:-1]

    return url


def _inside_www_token(text, start, end):
    token_start = start
    token_end = end

    while token_start > 0 and not text[token_start - 1].isspace():
        token_start -= 1

    while token_end < len(text) and not text[token_end].isspace():
        token_end += 1

    return "www." in text[token_start:token_end].lower()


def _link_text(
    text, *, link_mentions=True, excluded_mentions=(),
):
    """Link safe standalone URLs, FANZ mentions, and hashtags."""
    matches = []

    for match in WWW_TOKEN_RE.finditer(text):
        candidate = _trim_url_candidate(match.group(0))
        normalized_href = "https://" + candidate

        if not _is_valid_plaintext_www_url(
            candidate,
            normalized_href,
        ):
            continue

        matches.append(
            (
                match.start(),
                match.start() + len(candidate),
                "url",
                (candidate, normalized_href),
            )
        )

    for match in (MENTION_RE.finditer(text) if link_mentions else ()):
        if match.group(1).casefold() in excluded_mentions:
            continue

        if _inside_www_token(text, match.start(), match.end()):
            continue

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

    for match in BARE_FANZ_PATH_RE.finditer(text):
        matches.append(
            (
                match.start(),
                match.end(),
                "internal_path",
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

        if kind == "internal_path":
            path_value = match.group(0)

            # Never link only a prefix of a larger URL candidate.
            if (
                end < len(text)
                and not text[end].isspace()
                and (
                    text[end] not in ".,;!?"
                    or (
                        end + 1 < len(text)
                        and not text[end + 1].isspace()
                        and text[end + 1] not in ")]}"
                    )
                )
            ):
                rejected_end = end
                while (
                    rejected_end < len(text)
                    and not text[rejected_end].isspace()
                ):
                    rejected_end += 1

                parts.append(str(escape(text[start:rejected_end])))
                cursor = rejected_end
                continue

            safe_path = escape(path_value)
            parts.append(f'<a href="{safe_path}">{safe_path}</a>')
            cursor = end
            continue

        if kind == "url":
            value, href = match
            escaped_href = html_escape(href, quote=True)
            parts.append(
                f'<a href="{escaped_href}">'
                f'{escape(value)}</a>'
            )
        else:
            value = match.group(1)

            if kind == "mention":
                href = reverse(
                    "resolve_mention",
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

    def __init__(
        self, *, link_mentions=True, excluded_mentions=(),
    ):
        super().__init__(
            convert_charrefs=False,
        )

        self.parts = []
        self.skip_depth = 0
        self.link_mentions = link_mentions
        self.excluded_mentions = excluded_mentions
        self.text_buffer = []

    def _flush_text(self):
        if not self.text_buffer:
            return

        text = "".join(self.text_buffer)
        self.text_buffer.clear()

        if self.skip_depth:
            self.parts.append(str(escape(text)))
        else:
            self.parts.append(
                _link_text(
                    text,
                    link_mentions=self.link_mentions,
                    excluded_mentions=self.excluded_mentions,
                )
            )

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
        self._flush_text()
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
        self._flush_text()
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
        self._flush_text()
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
        self.text_buffer.append(data)

    def handle_entityref(
        self,
        name,
    ):
        if name == "amp":
            self.text_buffer.append("&")
            return

        self._flush_text()
        self.parts.append(f"&{name};")

    def handle_charref(
        self,
        name,
    ):
        self._flush_text()
        self.parts.append(f"&#{name};")

    def get_html(self):
        self._flush_text()
        return "".join(
            self.parts
        )


def _link_fanz_text_nodes(
    html, *, link_mentions=True, excluded_mentions=(),
):
    parser = _FanzTextLinkifier(
        link_mentions=link_mentions,
        excluded_mentions=excluded_mentions,
    )
    parser.feed(html)
    parser.close()

    return parser.get_html()


def _is_valid_plaintext_www_url(
    link_text,
    normalized_href,
):
    expected_href = "https://" + link_text

    return (
        normalized_href == expected_href
        and _is_valid_https_url(normalized_href)
    )


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

    # Reject ambiguous encoded separators in internal paths.
    decoded_path = urlsplit(href).path
    for _ in range(5):
        next_path = unquote(decoded_path)
        if next_path == decoded_path:
            break
        decoded_path = next_path

    has_unsafe_separator = (
        "\\" in decoded_path
        or "%2f" in decoded_path.lower()
        or "%5c" in decoded_path.lower()
    )

    is_internal = (
        href.startswith("/")
        and not href.startswith("//")
        and not has_unsafe_separator
        and "//" not in decoded_path
    )

    is_external_https = (
        parsed.scheme.lower()
        == "https"
        and bool(parsed.netloc)
        and _is_valid_https_url(href)
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

    return None


@register.filter
def render_post_content(value):
    return _render_post_content(value)


@register.filter
def render_marketing_content(value):
    return _render_post_content(value, link_mentions=False)


def render_legacy_marketing_content(value, promotional_token):
    """Suppress only an authorized legacy Founder promotional token."""
    token = str(promotional_token or "").casefold()

    if token not in {"name", "biz"}:
        return render_post_content(value)

    return _render_post_content(
        value,
        excluded_mentions=frozenset({token}),
    )


def _render_post_content(
    value, *, link_mentions=True, excluded_mentions=(),
):
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
        clean,
        link_mentions=link_mentions,
        excluded_mentions=excluded_mentions,
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
        url_re=HTTPS_TOKEN_RE,
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
def post_title_text(value):
    source = str(value or "").strip()
    words = source.split()

    while words and re.fullmatch(r"#[\w]{2,50}", words[-1]):
        words.pop()

    return " ".join(words)


@register.filter
def post_title_hashtags(value):
    words = str(value or "").strip().split()
    tags = []

    while words and re.fullmatch(r"#[\w]{2,50}", words[-1]):
        tags.insert(0, words.pop())

    return " ".join(tags)


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


def _split_post_presentation(post):
    """Separate authorized marketing content without changing storage."""
    from auctions.sunsetcam_cta import split_sunsetcam_marketing_suffix

    body = post_body(post.display_content)

    if post.is_paid:
        return body, ""

    user = post.user

    if user.username.casefold() != "sunsetcam":
        legacy = getattr(
            post, "legacy_marketing_presentation", None
        )

        if legacy is not None and post.is_public:
            return legacy.caption, legacy.suffix

        return body, ""

    profile = getattr(user, "profile", None)

    if not getattr(profile, "is_platform_account", False):
        return body, ""

    return split_sunsetcam_marketing_suffix(body)


@register.filter
def post_main_caption(post):
    body, _suffix = _split_post_presentation(post)
    return body


@register.filter
def post_marketing_suffix(post):
    _body, suffix = _split_post_presentation(post)
    return suffix


@register.filter
def render_post_marketing(post):
    """Render authorized marketing using its source-specific policy."""
    suffix = post_marketing_suffix(post)

    if not suffix:
        return ""

    legacy = getattr(
        post, "legacy_marketing_presentation", None
    )

    if (
        legacy is not None
        and post.user.username.casefold() != "sunsetcam"
        and suffix == legacy.suffix
    ):
        return render_legacy_marketing_content(
            suffix,
            legacy.promotional_token,
        )

    return render_marketing_content(
        post_marketing_flair(suffix)
    )


@register.filter
def post_marketing_flair(value):
    """Decorate a recognized marketing suffix for display only."""
    source = str(value or "")
    message, separator, link = source.rpartition("\n\n")

    if not separator or not message.strip() or not link.strip():
        return source

    prefix = "↳ 💋❤️😘 "
    signoff = "XOXO 💕"

    if not message.startswith(prefix):
        message = prefix + message

    if not message.endswith(signoff):
        if not message.rstrip().endswith("🔥"):
            message = message.rstrip() + " 🔥"

        message += " " + signoff

    return message + separator + link


@register.filter
def post_display_hashtags(post):
    """Merge associated and trailing hashtags for display only."""
    tags = []
    seen = set()

    def add(name):
        name = str(name)
        key = name.casefold()

        if name and key not in seen:
            seen.add(key)
            tags.append(name)

    for tag in post.hashtags.all():
        add(tag.name)

    trailing = post_trailing_hashtags(post.display_content)

    for token in trailing.split():
        add(token[1:])

    return tags


DM_HTTPS_URL_RE = re.compile(
    r"(?<![\w@=/:\"'])https://[^\s<>\"']+",
    re.IGNORECASE,
)

DM_TRAILING_PUNCTUATION = ".,!?;:"
DM_CLOSING_PAIRS = {
    ")": "(",
    "]": "[",
    "}": "{",
}
DM_HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9-]{1,63}$")
DM_INVALID_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _trim_dm_url(candidate):
    url = candidate.rstrip(DM_TRAILING_PUNCTUATION)

    while url and url[-1] in DM_CLOSING_PAIRS:
        closing = url[-1]
        opening = DM_CLOSING_PAIRS[closing]

        if url.count(closing) <= url.count(opening):
            break

        url = url[:-1]

    return url


def _is_valid_https_url(url):
    if any(ord(character) < 32 for character in url):
        return False

    if "\\" in url or DM_INVALID_PERCENT_RE.search(url):
        return False

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False

    if parsed.username is not None or parsed.password is not None:
        return False

    hostname = parsed.hostname

    if not hostname or port is not None and not 1 <= port <= 65535:
        return False

    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
        except ValueError:
            return False
        return True

    if re.fullmatch(r"[0-9.]+", hostname):
        try:
            ipaddress.IPv4Address(hostname)
        except ValueError:
            return False
        return True

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    labels = ascii_hostname.rstrip(".").split(".")

    return bool(labels) and all(
        DM_HOST_LABEL_RE.fullmatch(label)
        and not label.startswith("-")
        and not label.endswith("-")
        for label in labels
    )


def _escape_dm_text(value):
    return str(escape(value)).replace("\n", "<br>")


@register.filter
def render_dm_plaintext(value):
    """Safely render direct messages with validated HTTPS links."""
    if value is None:
        return ""

    source = str(value).replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    cursor = 0

    for match in DM_HTTPS_URL_RE.finditer(source):
        candidate = match.group(0)
        url = _trim_dm_url(candidate)

        if not url or not _is_valid_https_url(url):
            continue

        parts.append(_escape_dm_text(source[cursor:match.start()]))
        escaped_url = html_escape(url, quote=True)
        parts.append(
            f'<a href="{escaped_url}" target="_blank" '
            f'rel="noopener noreferrer ugc">{escaped_url}</a>'
        )
        cursor = match.start() + len(url)

    parts.append(_escape_dm_text(source[cursor:]))

    return mark_safe("".join(parts))


@register.filter
def render_fanz_plaintext(value):
    """Safely render user-controlled comments and replies."""
    if value is None:
        return ""

    source = str(value).replace("\r\n", "\n").replace("\r", "\n")

    return mark_safe(
        escape(source).replace("\n", "<br>")
    )


@register.filter
def render_fanz_preview(value):
    """Render a short, escaped message preview."""
    if value is None:
        return ""

    source = str(value).replace("\r\n", "\n").replace("\r", "\n")
    preview = " ".join(source.split())

    return escape(preview)
