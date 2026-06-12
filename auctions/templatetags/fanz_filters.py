from django import template

register = template.Library()


@register.filter
def compact_number(value):
    value = int(value)

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")

    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".rstrip("0").rstrip(".")

    if value >= 1_000:
        return f"{value / 1_000:.1f}K".rstrip("0").rstrip(".")

    return str(value)
