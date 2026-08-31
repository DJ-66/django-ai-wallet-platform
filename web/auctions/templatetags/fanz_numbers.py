from django import template


register = template.Library()


@register.filter
def compact_number(value):
    if value is None:
        return ""

    value = float(value)

    units = (
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    )

    for divisor, suffix in units:
        if abs(value) >= divisor:
            number = value / divisor

            if number.is_integer():
                return f"{int(number)}{suffix}"

            return (
                f"{number:.2f}"
                .rstrip("0")
                .rstrip(".")
                + suffix
            )

    if value.is_integer():
        return str(int(value))

    return str(value)
