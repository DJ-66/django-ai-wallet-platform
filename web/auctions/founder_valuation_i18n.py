# ---------------------------------------------------------
# FANZ Founder valuation presentation / localization
# ---------------------------------------------------------

SUPPORTED_LANGUAGES = ("en", "es", "pt")
DEFAULT_LANGUAGE = "en"


VALUATION_TEXT = {
    "en": {
        "founder_liquidity_pending": (
            "FANZ liquidity becomes available after the "
            "minimum holding period."
        ),
        "founder_liquidity_available": (
            "FANZ liquidity is currently available."
        ),
        "active_development_qualified": (
            "Active Development qualified."
        ),
        "active_development_not_qualified": (
            "Active Development not yet qualified."
        ),
        "intrinsic_structural_premium": (
            "This Founder property receives an intrinsic "
            "structural premium."
        ),
        "intrinsic_standard": (
            "This Founder property currently carries the "
            "standard intrinsic value."
        ),
        "passive_scarcity_appreciation": (
            "Founder scarcity and platform utility contribute "
            "to long-term estimated value."
        ),
        "active_development_growth": (
            "Qualified Active Development adds an earned "
            "growth accelerator."
        ),
    },

    "es": {
        "founder_liquidity_pending": (
            "La liquidez de FANZ estará disponible después "
            "del período mínimo de tenencia."
        ),
        "founder_liquidity_available": (
            "La liquidez de FANZ está disponible actualmente."
        ),
        "active_development_qualified": (
            "Desarrollo Activo calificado."
        ),
        "active_development_not_qualified": (
            "El Desarrollo Activo aún no está calificado."
        ),
        "intrinsic_structural_premium": (
            "Esta propiedad Founder recibe una prima "
            "estructural intrínseca."
        ),
        "intrinsic_standard": (
            "Esta propiedad Founder actualmente tiene el "
            "valor intrínseco estándar."
        ),
        "passive_scarcity_appreciation": (
            "La escasez Founder y la utilidad de la plataforma "
            "contribuyen al valor estimado a largo plazo."
        ),
        "active_development_growth": (
            "El Desarrollo Activo calificado añade un "
            "acelerador de crecimiento ganado."
        ),
    },

    "pt": {
        "founder_liquidity_pending": (
            "A liquidez FANZ ficará disponível após o "
            "período mínimo de posse."
        ),
        "founder_liquidity_available": (
            "A liquidez FANZ está disponível atualmente."
        ),
        "active_development_qualified": (
            "Desenvolvimento Ativo qualificado."
        ),
        "active_development_not_qualified": (
            "O Desenvolvimento Ativo ainda não está qualificado."
        ),
        "intrinsic_structural_premium": (
            "Esta propriedade Founder recebe um prêmio "
            "estrutural intrínseco."
        ),
        "intrinsic_standard": (
            "Esta propriedade Founder atualmente possui o "
            "valor intrínseco padrão."
        ),
        "passive_scarcity_appreciation": (
            "A escassez Founder e a utilidade da plataforma "
            "contribuem para o valor estimado de longo prazo."
        ),
        "active_development_growth": (
            "O Desenvolvimento Ativo qualificado adiciona um "
            "acelerador de crescimento conquistado."
        ),
    },
}


VALUATION_LABELS = {
    "en": {
        "estimated_value": "Estimated Value",
        "current_value": "Current Estimated Value",
        "intrinsic_value": "Intrinsic Value",
        "passive_value": "Scarcity / Platform Value",
        "development_value": "Development Value",
        "capital_basis": "Capital Basis",
        "buyback_floor": "FANZ Liquidity Floor",
        "actionable_floor": "Available FANZ Liquidity",
        "projected_2y": "2-Year Estimate",
        "projected_5y": "5-Year Estimate",
        "projected_10y": "10-Year Estimate",
    },

    "es": {
        "estimated_value": "Valor estimado",
        "current_value": "Valor estimado actual",
        "intrinsic_value": "Valor intrínseco",
        "passive_value": "Valor de escasez / plataforma",
        "development_value": "Valor de desarrollo",
        "capital_basis": "Base de capital",
        "buyback_floor": "Piso de liquidez FANZ",
        "actionable_floor": "Liquidez FANZ disponible",
        "projected_2y": "Estimación a 2 años",
        "projected_5y": "Estimación a 5 años",
        "projected_10y": "Estimación a 10 años",
    },

    "pt": {
        "estimated_value": "Valor estimado",
        "current_value": "Valor estimado atual",
        "intrinsic_value": "Valor intrínseco",
        "passive_value": "Valor de escassez / plataforma",
        "development_value": "Valor de desenvolvimento",
        "capital_basis": "Base de capital",
        "buyback_floor": "Piso de liquidez FANZ",
        "actionable_floor": "Liquidez FANZ disponível",
        "projected_2y": "Estimativa de 2 anos",
        "projected_5y": "Estimativa de 5 anos",
        "projected_10y": "Estimativa de 10 anos",
    },
}


def normalize_language(language):
    language = (language or DEFAULT_LANGUAGE).lower().strip()

    if "-" in language:
        language = language.split("-", 1)[0]

    if language not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE

    return language


def get_valuation_text(code, language="en"):
    language = normalize_language(language)

    return (
        VALUATION_TEXT.get(language, {}).get(code)
        or VALUATION_TEXT[DEFAULT_LANGUAGE].get(code)
        or code
    )


def get_valuation_label(key, language="en"):
    language = normalize_language(language)

    return (
        VALUATION_LABELS.get(language, {}).get(key)
        or VALUATION_LABELS[DEFAULT_LANGUAGE].get(key)
        or key
    )


def get_localized_valuation_presentation(
    valuation,
    language="en",
):
    language = normalize_language(language)

    presentation = valuation.get("presentation", {})

    liquidity_status = presentation.get(
        "liquidity_status"
    )

    development_status = presentation.get(
        "development_status"
    )

    reason_codes = presentation.get(
        "reason_codes",
        [],
    )

    return {
        "language": language,

        "valuation_version": presentation.get(
            "valuation_version"
        ),

        "labels": {
            key: get_valuation_label(
                key,
                language,
            )
            for key in VALUATION_LABELS[
                DEFAULT_LANGUAGE
            ]
        },

        "liquidity_status": {
            "code": liquidity_status,
            "text": get_valuation_text(
                liquidity_status,
                language,
            ),
        },

        "development_status": {
            "code": development_status,
            "text": get_valuation_text(
                development_status,
                language,
            ),
        },

        "reasons": [
            {
                "code": code,
                "text": get_valuation_text(
                    code,
                    language,
                ),
            }
            for code in reason_codes
        ],
    }
