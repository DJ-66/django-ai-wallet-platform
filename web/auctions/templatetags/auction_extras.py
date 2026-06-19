from django import template

register = template.Library()


@register.filter
def compact_number(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value

    if value < 1000:
        return str(value)

    if value < 10000:
        return f"{value // 100 / 10:.1f}K+"

    if value < 1000000:
        return f"{value // 1000}K+"

    if value < 10000000:
        return f"{value // 100000 / 10:.1f}M+"
