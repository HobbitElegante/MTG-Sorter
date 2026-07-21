from mtg_sorter.config import DEFAULT_LOCALE

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "MTG Commander Collection Manager",
        "tab.inventory": "Inventory",
        "tab.decks": "Decks",
        "tab.optimize": "Optimize",
        "tab.browse": "Browse",
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
        "config.language": "Language",
        "language.en": "English",
        "language.es": "Español",
        "common.refresh": "Refresh",
        "common.error": "Error",
        "common.success": "Success",
        "browse.section.overview": "Overview",
        "browse.section.cards": "Cards",
        "browse.section.decks": "Decks",
        "browse.section.inventory": "Inventory",
        "browse.section.scryfall": "Scryfall",
        "browse.overview.body": (
            "Cached cards: {cards}\n"
            "Physical copies: {copies} ({unassigned} unassigned)\n"
            "Decks: {decks} ({armed} armed)\n"
            "Deck list entries: {deck_cards}\n"
            "Copy assignments: {assignments}"
        ),
        "browse.cards.search": "Filter cards by name",
        "browse.cards.name": "Name",
        "browse.cards.type": "Type",
        "browse.cards.cmc": "CMC",
        "browse.cards.copies": "Copies",
        "browse.cards.flags": "Flags",
        "browse.decks.quantity": "Qty",
        "browse.decks.role": "Role",
        "browse.inventory.copy": "Copy #",
        "browse.inventory.assigned": "Assigned to",
        "browse.inventory.free": "Free",
        "browse.scryfall.sync": "Download oracle-cards bulk pack",
        "browse.scryfall.starting": "Starting Scryfall sync…",
        "browse.scryfall.done": "Imported {count:,} oracle cards.",
        "browse.scryfall.never": "Never",
        "browse.scryfall.status": (
            "Cached cards in database: {cached}\n"
            "Scryfall bulk updated at: {bulk_updated}\n"
            "Last local sync: {last_synced}\n"
            "Cards processed in last sync: {imported}"
        ),
        "browse.scryfall.info": (
            "Individual API lookups are saved in the local Card cache. "
            "Download the Scryfall oracle-cards bulk pack once to resolve "
            "imports and inventory searches offline."
        ),
    },
    "es": {
        "app.title": "Gestor de Colección Commander MTG",
        "tab.inventory": "Inventario",
        "tab.decks": "Mazos",
        "tab.optimize": "Optimizar",
        "tab.browse": "Explorar",
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
        "config.language": "Idioma",
        "language.en": "English",
        "language.es": "Español",
        "common.refresh": "Actualizar",
        "common.error": "Error",
        "common.success": "Éxito",
        "browse.section.overview": "Resumen",
        "browse.section.cards": "Cartas",
        "browse.section.decks": "Mazos",
        "browse.section.inventory": "Inventario",
        "browse.section.scryfall": "Scryfall",
        "browse.overview.body": (
            "Cartas en caché: {cards}\n"
            "Copias físicas: {copies} ({unassigned} libres)\n"
            "Mazos: {decks} ({armed} armados)\n"
            "Entradas en listas: {deck_cards}\n"
            "Asignaciones de copias: {assignments}"
        ),
        "browse.cards.search": "Filtrar cartas por nombre",
        "browse.cards.name": "Nombre",
        "browse.cards.type": "Tipo",
        "browse.cards.cmc": "CMC",
        "browse.cards.copies": "Copias",
        "browse.cards.flags": "Etiquetas",
        "browse.decks.quantity": "Cant.",
        "browse.decks.role": "Rol",
        "browse.inventory.copy": "Copia #",
        "browse.inventory.assigned": "Asignada a",
        "browse.inventory.free": "Libre",
        "browse.scryfall.sync": "Descargar pack bulk oracle-cards",
        "browse.scryfall.starting": "Iniciando sincronización con Scryfall…",
        "browse.scryfall.done": "Se importaron {count:,} cartas oracle.",
        "browse.scryfall.never": "Nunca",
        "browse.scryfall.status": (
            "Cartas en caché local: {cached}\n"
            "Bulk de Scryfall actualizado: {bulk_updated}\n"
            "Última sync local: {last_synced}\n"
            "Cartas procesadas en la última sync: {imported}"
        ),
        "browse.scryfall.info": (
            "Las búsquedas individuales por API se guardan en la caché local. "
            "Descarga el pack bulk oracle-cards de Scryfall una vez para "
            "importar y buscar cartas sin conexión."
        ),
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
