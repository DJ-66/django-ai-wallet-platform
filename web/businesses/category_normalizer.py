from unicodedata import combining, normalize

from .models import BusinessListing


CATEGORY_ALIASES = {
    # Restaurants — English
    "restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurants": BusinessListing.INDUSTRY_RESTAURANT,
    "eatery": BusinessListing.INDUSTRY_RESTAURANT,
    "food": BusinessListing.INDUSTRY_RESTAURANT,
    "family restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "asian restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "japanese restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "sushi restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "italian restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "mexican restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "hamburger restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "fast food": BusinessListing.INDUSTRY_RESTAURANT,
    "fast food restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "pizza": BusinessListing.INDUSTRY_RESTAURANT,
    "pizza restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "pizza takeout": BusinessListing.INDUSTRY_RESTAURANT,
    "pizzeria": BusinessListing.INDUSTRY_RESTAURANT,
    "barbecue": BusinessListing.INDUSTRY_RESTAURANT,
    "barbecue restaurant": BusinessListing.INDUSTRY_RESTAURANT,
    "bbq": BusinessListing.INDUSTRY_RESTAURANT,
    "grill": BusinessListing.INDUSTRY_RESTAURANT,
    "bar": BusinessListing.INDUSTRY_RESTAURANT,
    "bar & grill": BusinessListing.INDUSTRY_RESTAURANT,
    "gastropub": BusinessListing.INDUSTRY_RESTAURANT,
    "coffee shop": BusinessListing.INDUSTRY_RESTAURANT,
    "coffee store": BusinessListing.INDUSTRY_RESTAURANT,
    "cafe": BusinessListing.INDUSTRY_RESTAURANT,
    "cafeteria": BusinessListing.INDUSTRY_RESTAURANT,
    "bakery": BusinessListing.INDUSTRY_RESTAURANT,

    # Restaurants — Spanish
    "restaurante": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurantes": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante familiar": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante asiatico": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante japones": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante de sushi": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante italiano": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante mexicano": BusinessListing.INDUSTRY_RESTAURANT,
    "hamburgueseria": BusinessListing.INDUSTRY_RESTAURANT,
    "comida rapida": BusinessListing.INDUSTRY_RESTAURANT,
    "pizzeria": BusinessListing.INDUSTRY_RESTAURANT,
    "pizza para llevar": BusinessListing.INDUSTRY_RESTAURANT,
    "cafeteria": BusinessListing.INDUSTRY_RESTAURANT,
    "cafe": BusinessListing.INDUSTRY_RESTAURANT,
    "panaderia": BusinessListing.INDUSTRY_RESTAURANT,
    "confiteria": BusinessListing.INDUSTRY_RESTAURANT,
    "comedor": BusinessListing.INDUSTRY_RESTAURANT,
    "parrillada": BusinessListing.INDUSTRY_RESTAURANT,
    "parrilla": BusinessListing.INDUSTRY_RESTAURANT,
    "asador": BusinessListing.INDUSTRY_RESTAURANT,
    "churrasqueria": BusinessListing.INDUSTRY_RESTAURANT,
    "barbacoa": BusinessListing.INDUSTRY_RESTAURANT,
    "bar y parrilla": BusinessListing.INDUSTRY_RESTAURANT,
    "bar restaurante": BusinessListing.INDUSTRY_RESTAURANT,
    "gastropub": BusinessListing.INDUSTRY_RESTAURANT,
    "gastronomia": BusinessListing.INDUSTRY_RESTAURANT,

    # Restaurants — Portuguese
    "restaurante": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurantes": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante brasileiro": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante familiar": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante asiatico": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante japones": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante de sushi": BusinessListing.INDUSTRY_RESTAURANT,
    "restaurante italiano": BusinessListing.INDUSTRY_RESTAURANT,
    "hamburgueria": BusinessListing.INDUSTRY_RESTAURANT,
    "comida rapida": BusinessListing.INDUSTRY_RESTAURANT,
    "lanchonete": BusinessListing.INDUSTRY_RESTAURANT,
    "pizzaria": BusinessListing.INDUSTRY_RESTAURANT,
    "pizza para viagem": BusinessListing.INDUSTRY_RESTAURANT,
    "cafeteria": BusinessListing.INDUSTRY_RESTAURANT,
    "cafe": BusinessListing.INDUSTRY_RESTAURANT,
    "padaria": BusinessListing.INDUSTRY_RESTAURANT,
    "confeitaria": BusinessListing.INDUSTRY_RESTAURANT,
    "churrascaria": BusinessListing.INDUSTRY_RESTAURANT,
    "grelhados": BusinessListing.INDUSTRY_RESTAURANT,
    "bar e grill": BusinessListing.INDUSTRY_RESTAURANT,
    "bar e restaurante": BusinessListing.INDUSTRY_RESTAURANT,
    "gastropub": BusinessListing.INDUSTRY_RESTAURANT,
    "comida": BusinessListing.INDUSTRY_RESTAURANT,

    # Law — English
    "law office": BusinessListing.INDUSTRY_LAW_FIRM,
    "law firm": BusinessListing.INDUSTRY_LAW_FIRM,
    "attorney": BusinessListing.INDUSTRY_LAW_FIRM,
    "lawyer": BusinessListing.INDUSTRY_LAW_FIRM,
    "legal services": BusinessListing.INDUSTRY_LAW_FIRM,

    # Law — Spanish
    "abogado": BusinessListing.INDUSTRY_LAW_FIRM,
    "abogada": BusinessListing.INDUSTRY_LAW_FIRM,
    "abogados": BusinessListing.INDUSTRY_LAW_FIRM,
    "estudio juridico": BusinessListing.INDUSTRY_LAW_FIRM,
    "bufete juridico": BusinessListing.INDUSTRY_LAW_FIRM,
    "asesoria legal": BusinessListing.INDUSTRY_LAW_FIRM,
    "servicios juridicos": BusinessListing.INDUSTRY_LAW_FIRM,

    # Law — Portuguese
    "advogado": BusinessListing.INDUSTRY_LAW_FIRM,
    "advogada": BusinessListing.INDUSTRY_LAW_FIRM,
    "advogados": BusinessListing.INDUSTRY_LAW_FIRM,
    "escritorio juridico": BusinessListing.INDUSTRY_LAW_FIRM,
    "escritorio de advocacia": BusinessListing.INDUSTRY_LAW_FIRM,
    "servicos juridicos": BusinessListing.INDUSTRY_LAW_FIRM,

    # Real estate — English
    "real estate": BusinessListing.INDUSTRY_REAL_ESTATE,
    "real estate agency": BusinessListing.INDUSTRY_REAL_ESTATE,
    "realtor": BusinessListing.INDUSTRY_REAL_ESTATE,
    "property broker": BusinessListing.INDUSTRY_REAL_ESTATE,
    "real estate broker": BusinessListing.INDUSTRY_REAL_ESTATE,
    "commercial real estate agency": BusinessListing.INDUSTRY_REAL_ESTATE,

    # Real estate — Spanish
    "inmobiliaria": BusinessListing.INDUSTRY_REAL_ESTATE,
    "inmobiliarias": BusinessListing.INDUSTRY_REAL_ESTATE,
    "agencia inmobiliaria": BusinessListing.INDUSTRY_REAL_ESTATE,
    "agente inmobiliario": BusinessListing.INDUSTRY_REAL_ESTATE,
    "corredor inmobiliario": BusinessListing.INDUSTRY_REAL_ESTATE,
    "bienes raices": BusinessListing.INDUSTRY_REAL_ESTATE,
    "propiedades": BusinessListing.INDUSTRY_REAL_ESTATE,

    # Real estate — Portuguese
    "imobiliaria": BusinessListing.INDUSTRY_REAL_ESTATE,
    "imobiliarias": BusinessListing.INDUSTRY_REAL_ESTATE,
    "agencia imobiliaria": BusinessListing.INDUSTRY_REAL_ESTATE,
    "corretor de imoveis": BusinessListing.INDUSTRY_REAL_ESTATE,
    "corretora de imoveis": BusinessListing.INDUSTRY_REAL_ESTATE,
    "imoveis": BusinessListing.INDUSTRY_REAL_ESTATE,
}


def normalize_category_key(value):
    """
    Return a language- and accent-insensitive category lookup key.
    """
    value = " ".join(str(value or "").split()).casefold()

    return "".join(
        character
        for character in normalize("NFKD", value)
        if not combining(character)
    )


def normalize_category(raw_category):
    """
    Map an external category name to a FANZ BusinessListing industry.

    Return None when the category is unknown so the calling importer
    can decide whether to reject, skip, report, or classify it later.
    """
    key = normalize_category_key(raw_category)

    if not key:
        return None

    return CATEGORY_ALIASES.get(key)
