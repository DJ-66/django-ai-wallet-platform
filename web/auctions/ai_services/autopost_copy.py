"""Approved multilingual personality and affiliate CTA copy."""

PERSONALITY_COPY = {
    "flirty": {
        "en": (
            "Looking this good deserves a little applause. 😘",
            "My camera roll has a crush on me. 💋",
        ),
        "es": (
            "Verse así de bien merece unos aplausos. 😘",
            "Mi galería de fotos está enamorada de mí. 💋",
        ),
        "pt": (
            "Estar tão linda merece alguns aplausos. 😘",
            "Minha galeria de fotos está apaixonada por mim. 💋",
        ),
    },
    "snarky": {
        "en": (
            "I was going to be humble, but the lighting disagreed. 🙄",
            "Some call it attitude. I call it quality control. 💅",
        ),
        "es": (
            "Iba a ser humilde, pero la iluminación no estuvo de acuerdo. 🙄",
            "Algunos lo llaman actitud. Yo lo llamo control de calidad. 💅",
        ),
        "pt": (
            "Eu ia ser humilde, mas a iluminação discordou. 🙄",
            "Alguns chamam de atitude. Eu chamo de controle de qualidade. 💅",
        ),
    },
    "savage": {
        "en": (
            "Not everyone can handle this level of fabulous. 🔥",
            "Some people bring drama. I bring better lighting. 😎",
        ),
        "es": (
            "No todos soportan este nivel de glamour. 🔥",
            "Algunos traen drama. Yo traigo mejor iluminación. 😎",
        ),
        "pt": (
            "Nem todo mundo aguenta esse nível de glamour. 🔥",
            "Alguns trazem drama. Eu trago uma iluminação melhor. 😎",
        ),
    },
    "dominatrix": {
        "en": (
            "Admire the view, darling. Good taste is expected. 👑",
            "Attention is earned. Remember your manners. 🖤",
        ),
        "es": (
            "Admira la vista, cariño. Se espera buen gusto. 👑",
            "La atención se gana. Recuerda tus modales. 🖤",
        ),
        "pt": (
            "Admire a vista, querido. Bom gosto é obrigatório. 👑",
            "Atenção se conquista. Lembre-se das boas maneiras. 🖤",
        ),
    },
}

CTA_COPY = {
    "founder": {
        "flirty": {
            "en": ("Your perfect @name is waiting. Go claim it, darling. 😘",),
            "es": ("Tu @name perfecto te espera. Reclámalo, cariño. 😘",),
            "pt": ("Seu @name perfeito está esperando. Garanta o seu, querido. 😘",),
        },
        "snarky": {
            "en": ("Your @name is still available? Interesting strategy. 🙄",),
            "es": ("¿Tu @name sigue disponible? Qué estrategia tan curiosa. 🙄",),
            "pt": ("Seu @name ainda está disponível? Estratégia curiosa. 🙄",),
        },
        "savage": {
            "en": ("Own your @biz before someone builds a better brand with it. 🔥",),
            "es": ("Consigue tu @biz antes de que alguien cree una marca mejor. 🔥",),
            "pt": ("Garanta seu @biz antes que alguém crie uma marca melhor. 🔥",),
        },
        "dominatrix": {
            "en": ("Claim your @name. That's an instruction, darling. 👑",),
            "es": ("Reclama tu @name. Es una orden, cariño. 👑",),
            "pt": ("Garanta seu @name. É uma ordem, querido. 👑",),
        },
    },
    "credits": {
        "flirty": {
            "en": ("Buy FANZ Credits. My tip jar loves attention. 💋",),
            "es": ("Compra FANZ Credits. Mi bote de propinas adora la atención. 💋",),
            "pt": ("Compre FANZ Credits. Meu pote de gorjetas adora atenção. 💋",),
        },
        "snarky": {
            "en": ("Buy FANZ Credits. My sarcasm is free; premium isn't. 💅",),
            "es": ("Compra FANZ Credits. Mi sarcasmo es gratis; lo premium no. 💅",),
            "pt": ("Compre FANZ Credits. Meu sarcasmo é grátis; o premium não. 💅",),
        },
        "savage": {
            "en": ("Still browsing without credits? Bold choice. 🔥",),
            "es": ("¿Sigues navegando sin créditos? Qué atrevido. 🔥",),
            "pt": ("Ainda navegando sem créditos? Que ousadia. 🔥",),
        },
        "dominatrix": {
            "en": ("Get your FANZ Credits. Come prepared, darling. 👑",),
            "es": ("Consigue tus FANZ Credits. Ven preparado, cariño. 👑",),
            "pt": ("Garanta seus FANZ Credits. Venha preparado, querido. 👑",),
        },
    },
    "autopost": {
        "flirty": {
            "en": ("Let AutoPost handle the captions. You handle the charm. 😘",),
            "es": ("Deja que AutoPost escriba. Tú encárgate del encanto. 😘",),
            "pt": ("Deixe o AutoPost escrever. Você cuida do charme. 😘",),
        },
        "snarky": {
            "en": ("Still posting manually? That's adorable. Try AutoPost. 🙄",),
            "es": ("¿Aún publicas manualmente? Qué adorable. Prueba AutoPost. 🙄",),
            "pt": ("Ainda publica manualmente? Que fofo. Experimente AutoPost. 🙄",),
        },
        "savage": {
            "en": ("AutoPost handles three languages. Your excuses handle none. 🔥",),
            "es": ("AutoPost domina tres idiomas. Tus excusas, ninguno. 🔥",),
            "pt": ("AutoPost domina três idiomas. Suas desculpas, nenhum. 🔥",),
        },
        "dominatrix": {
            "en": ("Put your publishing schedule under control. Use AutoPost. 👑",),
            "es": ("Pon tu calendario de publicaciones bajo control. Usa AutoPost. 👑",),
            "pt": ("Coloque sua agenda de publicações sob controle. Use AutoPost. 👑",),
        },
    },
}

def get_approved_suffix(
    *,
    kind: str,
    personality: str,
    campaign: str | None,
    language: str,
    variant_index: int,
) -> str:
    """Return preapproved suffix text for a selected post."""
    if kind == "personality":
        variants = PERSONALITY_COPY[personality][language]
    elif kind == "cta" and campaign in CTA_COPY:
        variants = CTA_COPY[campaign][personality][language]
    else:
        raise ValueError("Unsupported AutoPost suffix selection")

    if not 0 <= variant_index < len(variants):
        raise ValueError("Invalid AutoPost variant index")

    return variants[variant_index]


def get_variant_count(
    *,
    kind: str,
    personality: str,
    campaign: str | None = None,
) -> int:
    """Return the number of approved, aligned language variants."""
    if kind == "personality":
        languages = PERSONALITY_COPY[personality]
    elif kind == "cta" and campaign in CTA_COPY:
        languages = CTA_COPY[campaign][personality]
    else:
        raise ValueError("Unsupported AutoPost suffix selection")

    counts = {len(languages[lang]) for lang in ("en", "es", "pt")}
    if len(counts) != 1 or not next(iter(counts)):
        raise ValueError("AutoPost language variants are misaligned")

    return next(iter(counts))


def get_variant_count(
    *,
    kind: str,
    personality: str,
    campaign: str | None = None,
) -> int:
    """Return the number of approved, aligned language variants."""
    if kind == "personality":
        languages = PERSONALITY_COPY[personality]
    elif kind == "cta" and campaign in CTA_COPY:
        languages = CTA_COPY[campaign][personality]
    else:
        raise ValueError("Unsupported AutoPost suffix selection")

    counts = {len(languages[lang]) for lang in ("en", "es", "pt")}
    if len(counts) != 1 or not next(iter(counts)):
        raise ValueError("AutoPost language variants are misaligned")

    return next(iter(counts))
