"""Approved FANZ promotional campaign copy.

These are templates, not AI-generated claims.
Offers must be verified before public activation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Campaign:
    key: str
    copy: dict
    requires_offer_verification: bool = False


CAMPAIGNS = {
    "join": Campaign(
        key="join",
        copy={
            "en": ("Join FANZ for Free!", "Join Free"),
            "es": ("¡Únete a FANZ Gratis!", "Regístrate"),
            "pt": ("Entre na FANZ Grátis!", "Cadastre-se"),
        },
    ),
    "welcome": Campaign(
        key="welcome",
        requires_offer_verification=True,
        copy={
            "en": ("Get 50 Free Credits!", "Join FANZ"),
            "es": ("¡Recibe 50 Créditos Gratis!", "Únete"),
            "pt": ("Ganhe 50 Créditos Grátis!", "Cadastre-se"),
        },
    ),
    "referral": Campaign(
        key="referral",
        requires_offer_verification=True,
        copy={
            "en": ("Invite a Friend. 50 Credits Each!", "Invite & Earn"),
            "es": ("¡Invita a un Amigo! 50 Créditos Cada Uno", "Invita y Gana"),
            "pt": ("Convide um Amigo! 50 Créditos Cada", "Convide e Ganhe"),
        },
    ),
    "username": Campaign(
        key="username",
        copy={
            "en": ("Claim Your FANZ @Name!", "Join Free"),
            "es": ("¡Consigue Tu @Nombre FANZ!", "Regístrate"),
            "pt": ("Garanta Seu @Nome FANZ!", "Cadastre-se"),
        },
    ),
    "community": Campaign(
        key="community",
        copy={
            "en": ("Discover Your FANZ Community!", "Join Now"),
            "es": ("¡Descubre Tu Comunidad FANZ!", "Únete Ahora"),
            "pt": ("Descubra Sua Comunidade FANZ!", "Entre Agora"),
        },
    ),
    "business": Campaign(
        key="business",
        requires_offer_verification=True,
        copy={
            "en": ("List Your Business FREE for Life!", "List for Free"),
            "es": ("¡Anuncia Tu Negocio Gratis de Por Vida!", "Publica Gratis"),
            "pt": ("Anuncie Seu Negócio Grátis Para Sempre!", "Anuncie Grátis"),
        },
    ),
}


def get_campaign_copy(
    campaign_key,
    language,
    *,
    verified_offers=None,
):
    campaign = CAMPAIGNS[campaign_key]

    if language not in ("en", "es", "pt"):
        raise ValueError("Unsupported campaign language.")

    if campaign.requires_offer_verification:
        if campaign_key not in (verified_offers or set()):
            raise ValueError(
                f"Campaign '{campaign_key}' requires "
                "verified offer approval."
            )

    return campaign.copy[language]



# Approved localized feed captions.
# Restricted offers remain subject to campaign approval.
CAMPAIGN_CAPTIONS = {
    "join": {
        "en": (
            "Join FANZ for free! Discover creators, connect "
            "with the community, and claim your @name. "
            "#FANZ #JoinFANZ"
        ),
        "es": (
            "¡Únete gratis a FANZ! Descubre creadores, "
            "conecta con la comunidad y consigue tu @nombre. "
            "#FANZ #JoinFANZ"
        ),
        "pt": (
            "Entre grátis na FANZ! Descubra criadores, "
            "conecte-se com a comunidade e garanta seu @nome. "
            "#FANZ #JoinFANZ"
        ),
    },
    "welcome": {
        "en": "Join FANZ and discover your welcome credits. #FANZ",
        "es": "Únete a FANZ y descubre tus créditos de bienvenida. #FANZ",
        "pt": "Entre na FANZ e conheça seus créditos de boas-vindas. #FANZ",
    },
    "referral": {
        "en": "Invite friends to FANZ and discover referral rewards. #FANZ",
        "es": "Invita amigos a FANZ y descubre las recompensas. #FANZ",
        "pt": "Convide amigos para a FANZ e descubra as recompensas. #FANZ",
    },
    "username": {
        "en": "Your FANZ @name could be waiting. Check availability and join free! #FANZ",
        "es": "Tu @nombre en FANZ podría estar disponible. ¡Compruébalo y únete gratis! #FANZ",
        "pt": "Seu @nome na FANZ pode estar disponível. Confira e entre grátis! #FANZ",
    },
    "community": {
        "en": "Discover creators and connect with the FANZ community. Join free! #FANZ",
        "es": "Descubre creadores y conecta con la comunidad FANZ. ¡Únete gratis! #FANZ",
        "pt": "Descubra criadores e conecte-se com a comunidade FANZ. Entre grátis! #FANZ",
    },
    "business": {
        "en": "Help customers discover your business on FANZ. #FANZ",
        "es": "Ayuda a los clientes a descubrir tu negocio en FANZ. #FANZ",
        "pt": "Ajude clientes a descobrir sua empresa na FANZ. #FANZ",
    },
}


def get_campaign_caption(
    campaign_key,
    language,
    *,
    verified_offers=None,
):
    # Reuse the existing campaign approval and language checks.
    get_campaign_copy(
        campaign_key,
        language,
        verified_offers=verified_offers,
    )

    return CAMPAIGN_CAPTIONS[campaign_key][language]
