"""Curated multilingual CTAs for platform-owned SunsetCam posts."""

from auctions.ai_services.cta_links import labeled_link


LANGUAGES = ("en", "es", "pt")

CAMPAIGN_ORDER = (
    "business",
    "identity",
    "real_estate",
)

DESTINATIONS = {
    "business": "/b/create/",
    "identity": "/founder/tienda/",
    "real_estate": "/founder/tienda/",
}

LABELS = {
    "business": {
        "en": "List My Biz",
        "es": "Publica Tu Negocio",
        "pt": "Cadastre Seu Negócio",
    },
    "identity": {
        "en": "Claim Your @Name",
        "es": "Reclama Tu @Nombre",
        "pt": "Garanta Seu @Nome",
    },
    "real_estate": {
        "en": "Explore Digital Real Estate",
        "es": "Explora Propiedades Digitales",
        "pt": "Explore Imóveis Digitais",
    },
}

COPY = {
    "business": (
        {
            "en": "List your business on FANZ. Siempre gratis. ❤️",
            "es": "Publica tu negocio en FANZ. Siempre gratis. ❤️",
            "pt": "Cadastre seu negócio no FANZ. Sempre grátis. ❤️",
        },
        {
            "en": "Your business. Your @name. Your future. ❤️",
            "es": "Tu negocio. Tu @nombre. Tu futuro. ❤️",
            "pt": "Seu negócio. Seu @nome. Seu futuro. ❤️",
        },
        {
            "en": "Get discovered. Grow your business on FANZ. 🔥",
            "es": "Date a conocer. Haz crecer tu negocio en FANZ. 🔥",
            "pt": "Seja descoberto. Faça seu negócio crescer no FANZ. 🔥",
        },
        {
            "en": "Local business. Global ambitions. List for free. ❤️",
            "es": "Negocio local. Ambiciones globales. Publica gratis. ❤️",
            "pt": "Negócio local. Ambições globais. Cadastre-se grátis. ❤️",
        },
    ),
    "identity": (
        {
            "en": "One @name. One identity. One of a @kind. Just like @you. ❤️",
            "es": "Un @nombre. Una identidad. Única. Como @tú. ❤️",
            "pt": "Um @nome. Uma identidade. Única. Como @você. ❤️",
        },
        {
            "en": "The internet is infinite. Your @name isn't. 🔥",
            "es": "Internet es infinito. Tu @nombre no. 🔥",
            "pt": "A internet é infinita. Seu @nome não. 🔥",
        },
        {
            "en": "Make a name for yourself. Literally. 😉",
            "es": "Hazte un nombre. Literalmente. 😉",
            "pt": "Faça seu próprio nome. Literalmente. 😉",
        },
        {
            "en": "Come for the @name. Stay for the people. ❤️",
            "es": "Ven por tu @nombre. Quédate por la gente. ❤️",
            "pt": "Venha pelo @nome. Fique pelas pessoas. ❤️",
        },
    ),
    "real_estate": (
        {
            "en": "Every @name is unique. Not every @name is for sale.",
            "es": "Cada @nombre es único. No todos están a la venta.",
            "pt": "Cada @nome é único. Nem todos estão à venda.",
        },
        {
            "en": "Get @it before it's @gone. 🔥",
            "es": "Consigue tu @nombre antes de que desaparezca. 🔥",
            "pt": "Garanta seu @nome antes que alguém o escolha. 🔥",
        },
        {
            "en": "Build your brand. Own your corner of the internet. ❤️",
            "es": "Construye tu marca. Haz tuyo un rincón de internet. ❤️",
            "pt": "Construa sua marca. Tenha seu espaço na internet. ❤️",
        },
        {
            "en": "Don't just own something scarce. Make it worth owning. 🔥",
            "es": "No basta con tener algo escaso. Haz que valga la pena. 🔥",
            "pt": "Não basta possuir algo raro. Faça valer a pena. 🔥",
        },
    ),
}


def select_campaign(capture_number):
    """Select a deterministic campaign and aligned copy variant."""
    if type(capture_number) is not int or capture_number < 1:
        raise ValueError("Capture number must be a positive integer")

    index = capture_number - 1
    campaign = CAMPAIGN_ORDER[index % len(CAMPAIGN_ORDER)]
    variants = COPY[campaign]
    variant_index = (index // len(CAMPAIGN_ORDER)) % len(variants)

    return campaign, variant_index


def decorate_sunsetcam_caption(*, content, language, capture_number):
    """Insert one localized CTA before the original hashtag line."""
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")

    if not isinstance(content, str) or "\n\n" not in content:
        raise ValueError("Invalid SunsetCam caption")

    caption, hashtag_line = content.rsplit("\n\n", 1)

    if not caption.strip() or not hashtag_line.strip():
        raise ValueError("Empty caption or hashtag line")

    if not all(tag.startswith("#") for tag in hashtag_line.split()):
        raise ValueError("Invalid hashtag line")

    campaign, variant_index = select_campaign(capture_number)

    message = COPY[campaign][variant_index][language]

    link = labeled_link(
        LABELS[campaign][language],
        DESTINATIONS[campaign],
    )

    if link in caption:
        raise ValueError("SunsetCam CTA already applied")

    decorated = (
        caption
        + "\n\n"
        + message
        + "\n\n"
        + link
        + "\n\n"
        + hashtag_line
    )

    if len(decorated) > 2500:
        raise ValueError("Decorated caption exceeds 2500 characters")

    return decorated
