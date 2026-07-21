from mtg_sorter.config import DEFAULT_LOCALE

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "MTG Commander Collection Manager",
        "tab.inventory": "Inventory",
        "tab.decks": "Decks",
        "tab.optimize": "Optimize",
        "inventory.search": "Search card on Scryfall",
        "inventory.add": "Add to inventory",
        "inventory.quantity": "Quantity",
        "inventory.empty": "No unassigned copies in inventory.",
        "decks.import": "Import Moxfield list",
        "decks.name": "Deck name",
        "decks.commander": "Commander name (optional)",
        "decks.status.armed": "Armed",
        "decks.status.dismantled": "Dismantled",
        "decks.set_armed": "Mark armed",
        "decks.set_dismantled": "Mark dismantled",
        "decks.empty": "No decks imported yet.",
        "optimize.target": "Deck to assemble",
        "optimize.run": "Find optimal dismantle plan",
        "optimize.no_solutions": "No feasible dismantle plan found.",
        "optimize.multiple": "Multiple optimal plans — choose one:",
        "optimize.from_inventory": "Cards covered by free inventory",
        "optimize.decks_to_dismantle": "Decks to dismantle",
        "optimize.missing": "Still missing",
        "menu.language": "Language",
        "language.en": "English",
        "language.es": "Español",
        "common.refresh": "Refresh",
        "common.error": "Error",
        "common.success": "Success",
    },
    "es": {
        "app.title": "Gestor de Colección Commander MTG",
        "tab.inventory": "Inventario",
        "tab.decks": "Mazos",
        "tab.optimize": "Optimizar",
        "inventory.search": "Buscar carta en Scryfall",
        "inventory.add": "Añadir al inventario",
        "inventory.quantity": "Cantidad",
        "inventory.empty": "No hay copias libres en el inventario.",
        "decks.import": "Importar lista Moxfield",
        "decks.name": "Nombre del mazo",
        "decks.commander": "Nombre del commander (opcional)",
        "decks.status.armed": "Armado",
        "decks.status.dismantled": "Desarmado",
        "decks.set_armed": "Marcar armado",
        "decks.set_dismantled": "Marcar desarmado",
        "decks.empty": "Aún no hay mazos importados.",
        "optimize.target": "Mazo a armar",
        "optimize.run": "Calcular plan óptimo",
        "optimize.no_solutions": "No hay plan viable de desmontaje.",
        "optimize.multiple": "Hay varios planes óptimos — elige uno:",
        "optimize.from_inventory": "Cartas cubiertas por inventario libre",
        "optimize.decks_to_dismantle": "Mazos a desarmar",
        "optimize.missing": "Aún faltan",
        "menu.language": "Idioma",
        "language.en": "English",
        "language.es": "Español",
        "common.refresh": "Actualizar",
        "common.error": "Error",
        "common.success": "Éxito",
    },
}


class Translator:
    def __init__(self, locale: str = DEFAULT_LOCALE) -> None:
        self._locale = locale if locale in TRANSLATIONS else DEFAULT_LOCALE

    @property
    def locale(self) -> str:
        return self._locale

    def set_locale(self, locale: str) -> None:
        if locale in TRANSLATIONS:
            self._locale = locale

    def t(self, key: str) -> str:
        return TRANSLATIONS[self._locale].get(
            key,
            TRANSLATIONS[DEFAULT_LOCALE].get(key, key),
        )
