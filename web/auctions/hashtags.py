import re

from .models import Hashtag

HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]{2,50})")


def extract_hashtag_names(text):
    if not text:
        return []

    names = []
    seen = set()

    for match in HASHTAG_RE.findall(text):
        name = match.lower().strip("_")

        if name and name not in seen:
            names.append(name)
            seen.add(name)

    return names


def sync_post_hashtags(post):
    names = extract_hashtag_names(f"{post.title} {post.content}")

    tags = []
    for name in names:
        tag, _created = Hashtag.objects.get_or_create(name=name)
        tags.append(tag)

    post.hashtags.set(tags)

    for tag in tags:
        tag.usage_count = tag.posts.count()
        tag.save(update_fields=["usage_count"])
