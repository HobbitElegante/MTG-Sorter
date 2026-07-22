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
        "inventory.summary.title": "Collection summary",
        "inventory.summary.empty": "No physical copies registered yet. Import a deck to start mapping your collection.",
        "inventory.summary.body": (
            "{unique} unique cards · {copies} physical copies · "
            "{free} free · {assigned} assigned to armed decks"
        ),
        "inventory.search.collection": "Search your collection…",
        "inventory.search.hint": "Type a card name to check whether you have free copies.",
        "inventory.add_new": "Add new card to collection",
        "inventory.edit_copies": "Edit copy count",
        "inventory.add_dialog.title": "Add card to collection",
        "inventory.add_dialog.search": "Search card name",
        "inventory.add_dialog.copies": "Copies to add",
        "inventory.add_dialog.confirm": "Add copies",
        "inventory.add_dialog.no_selection": "Select a card from the search results.",
        "inventory.edit_dialog.title": "Edit copy count",
        "inventory.edit_dialog.card": "Card",
        "inventory.edit_dialog.total": "Total copies",
        "inventory.edit_dialog.assigned_note": (
            "{count} cop(y/ies) are assigned to armed decks and cannot be removed here."
        ),
        "inventory.status.available": "Available — {count} free",
        "inventory.status.unavailable": "Not available — all {count} assigned",
        "inventory.not_owned": "That card is not in your collection.",
        "inventory.matches": "{count} matching cards in your collection.",
        "decks.import": "Import Moxfield list",
        "decks.name": "Deck name",
        "decks.commander": "Commander name (optional)",
        "decks.status.armed": "Armed",
        "decks.status.dismantled": "Dismantled",
        "decks.set_armed": "Mark armed",
        "decks.set_dismantled": "Mark dismantled",
        "decks.empty": "No decks imported yet.",
        "decks.details": "{name}: {count} list entries",
        "decks.details.armed": "{count} list entries — complete",
        "decks.details.dismantled": "{count} list entries — {available} cards available",
        "decks.import.status.title": "Deck status",
        "decks.import.status.question": "Is this deck currently armed or dismantled?",
        "decks.import.available.title": "Available cards",
        "decks.import.available.question": (
            "Which cards from this list do you still have available in your collection?"
        ),
        "decks.import.available.in_list": "In list",
        "decks.import.available.available": "Available",
        "decks.import.available.all": "Mark all available",
        "decks.list.title": "Your decks",
        "decks.edit_list": "Edit list",
        "decks.delete_list": "Delete list",
        "decks.delete.confirm.title": "Delete deck list",
        "decks.delete.confirm.question": (
            "Delete “{name}”? Choose below how many physical copies to remove "
            "with the list."
        ),
        "decks.delete.copies.hint": (
            "You can remove all removable copies, some, or none. "
            "If Quitar stays at 0, those copies belong to other armed decks."
        ),
        "decks.delete.copies.inventory": "In inventory",
        "decks.delete.copies.inventory_elsewhere": "{total} ({elsewhere} in other decks)",
        "decks.delete.copies.elsewhere_tip": (
            "{count} cop(y/ies) assigned to other armed decks and cannot be removed here."
        ),
        "decks.delete.copies.remove": "Remove",
        "decks.delete.copies.remaining": "Remaining",
        "decks.delete.copies.keep_all": "Keep all copies",
        "decks.delete.copies.remove_all": "Remove all removable",
        "decks.show_import": "Import Moxfield list",
        "decks.load_file": "Load file",
        "decks.submit_import": "Confirm list",
        "decks.cancel_import": "Cancel",
        "decks.load_file.dialog_title": "Open Moxfield export",
        "decks.edit.title": "Edit deck list",
        "decks.edit.save": "Save list",
        "decks.edit.total": "Cards in list: {current} / {target}",
        "decks.edit.slots": "Open slots: {slots}",
        "decks.edit.free": "Free",
        "decks.edit.replace": "Replace",
        "decks.edit.add": "Add card",
        "decks.edit.add.title": "Add card to list",
        "decks.edit.replace.title": "Replace card",
        "decks.edit.search": "Search card name",
        "decks.edit.quantity": "Quantity in list",
        "decks.edit.available": "Available copies (0 = missing)",
        "decks.edit.remove_outgoing": "Also remove copies of the outgoing card",
        "decks.edit.remove_outgoing_qty": "Copies to remove",
        "decks.edit.pick": "Use selected card",
        "decks.edit.no_selection": "Select a card from the search results.",
        "decks.edit.over_target": "List total cannot exceed the original size.",
        "optimize.target": "Deck to assemble",
        "optimize.run": "Find optimal dismantle plan",
        "optimize.no_solutions": "No feasible dismantle plan found.",
        "optimize.already_armed": "This deck is already armed — nothing to optimize.",
        "optimize.multiple": "Multiple optimal plans — choose one:",
        "optimize.from_inventory": "Cards covered by free inventory",
        "optimize.decks_to_dismantle": "Decks to dismantle",
        "optimize.missing": "Still missing",
        "optimize.unit.cards": "cards",
        "optimize.unit.decks": "decks",
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
        "browse.section.availability": "Availability",
        "browse.section.scryfall": "Scryfall",
        "browse.overview.greeting": (
            " __  __  _______   _____          _____\n"
            "|  \\/  ||__   __| / ____|        / ____|\n"
            "| \\  / |   | |   | |  __ ______ | (___\n"
            "| |\\/| |   | |   | | |_ |______| \\___ \\\n"
            "| |  | |   | |   | |__| |       ____) |\n"
            "|_|  |_|   |_|    \\_____|      |_____/"
        ),
        "browse.overview.tagline": "Commander Collection Manager",
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
        "browse.cards.flag.basic": "basic",
        "browse.cards.flag.token": "token",
        "browse.decks.quantity": "Qty",
        "browse.decks.role": "Role",
        "browse.inventory.copy": "Copy #",
        "browse.inventory.copies": "Copies",
        "browse.inventory.mixed": "{free} free · {decks}",
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
        "inventory.summary.title": "Resumen de la colección",
        "inventory.summary.empty": (
            "Aún no hay copias físicas registradas. Importa un mazo para empezar a mapear tu colección."
        ),
        "inventory.summary.body": (
            "{unique} cartas únicas · {copies} copias físicas · "
            "{free} libres · {assigned} asignadas a mazos armados"
        ),
        "inventory.search.collection": "Buscar en tu colección…",
        "inventory.search.hint": "Escribe el nombre de una carta para ver si tienes copias libres.",
        "inventory.add_new": "Agregar carta nueva a la colección",
        "inventory.edit_copies": "Editar el número de copias",
        "inventory.add_dialog.title": "Agregar carta a la colección",
        "inventory.add_dialog.search": "Buscar carta por nombre",
        "inventory.add_dialog.copies": "Copias a agregar",
        "inventory.add_dialog.confirm": "Agregar copias",
        "inventory.add_dialog.no_selection": "Selecciona una carta de los resultados.",
        "inventory.edit_dialog.title": "Editar el número de copias",
        "inventory.edit_dialog.card": "Carta",
        "inventory.edit_dialog.total": "Copias totales",
        "inventory.edit_dialog.assigned_note": (
            "{count} copia(s) están asignadas a mazos armados y no se pueden quitar aquí."
        ),
        "inventory.status.available": "Disponible — {count} libre(s)",
        "inventory.status.unavailable": "No disponible — las {count} copia(s) están asignadas",
        "inventory.not_owned": "Esa carta no está en tu colección.",
        "inventory.matches": "{count} cartas coinciden en tu colección.",
        "decks.import": "Importar lista Moxfield",
        "decks.name": "Nombre del mazo",
        "decks.commander": "Nombre del commander (opcional)",
        "decks.status.armed": "Armado",
        "decks.status.dismantled": "Desarmado",
        "decks.set_armed": "Marcar armado",
        "decks.set_dismantled": "Marcar desarmado",
        "decks.empty": "Aún no hay mazos importados.",
        "decks.details": "{name}: {count} entradas en el listado",
        "decks.details.armed": "{count} entradas en el listado — completado",
        "decks.details.dismantled": "{count} entradas en el listado — {available} cartas disponibles",
        "decks.import.status.title": "Estado del mazo",
        "decks.import.status.question": "¿Este mazo está armado o desarmado?",
        "decks.import.available.title": "Cartas disponibles",
        "decks.import.available.question": (
            "¿Cuáles cartas de este listado sigues teniendo disponibles en tu colección?"
        ),
        "decks.import.available.in_list": "En listado",
        "decks.import.available.available": "Disponibles",
        "decks.import.available.all": "Marcar todas disponibles",
        "decks.list.title": "Tus mazos",
        "decks.edit_list": "Editar listado",
        "decks.delete_list": "Eliminar listado",
        "decks.delete.confirm.title": "Eliminar listado",
        "decks.delete.confirm.question": (
            "¿Eliminar “{name}”? Elige abajo cuántas copias físicas quitar "
            "junto con el listado."
        ),
        "decks.delete.copies.hint": (
            "Puedes quitar todas las copias eliminables, algunas o ninguna. "
            "Si Quitar se queda en 0, esas copias están en otros mazos armados."
        ),
        "decks.delete.copies.inventory": "En inventario",
        "decks.delete.copies.inventory_elsewhere": "{total} ({elsewhere} en otros mazos)",
        "decks.delete.copies.elsewhere_tip": (
            "{count} copia(s) asignada(s) a otros mazos armados; no se pueden quitar aquí."
        ),
        "decks.delete.copies.remove": "Quitar",
        "decks.delete.copies.remaining": "Quedarían",
        "decks.delete.copies.keep_all": "Conservar todas las copias",
        "decks.delete.copies.remove_all": "Quitar todas las eliminables",
        "decks.show_import": "Importar lista Moxfield",
        "decks.load_file": "Cargar archivo",
        "decks.submit_import": "Confirmar listado",
        "decks.cancel_import": "Cancelar",
        "decks.load_file.dialog_title": "Abrir export de Moxfield",
        "decks.edit.title": "Editar listado del mazo",
        "decks.edit.save": "Guardar listado",
        "decks.edit.total": "Cartas en listado: {current} / {target}",
        "decks.edit.slots": "Huecos libres: {slots}",
        "decks.edit.free": "Libres",
        "decks.edit.replace": "Reemplazar",
        "decks.edit.add": "Añadir carta",
        "decks.edit.add.title": "Añadir carta al listado",
        "decks.edit.replace.title": "Reemplazar carta",
        "decks.edit.search": "Buscar carta por nombre",
        "decks.edit.quantity": "Cantidad en listado",
        "decks.edit.available": "Copias disponibles (0 = faltan)",
        "decks.edit.remove_outgoing": "También quitar copias de la carta que sale",
        "decks.edit.remove_outgoing_qty": "Copias a quitar",
        "decks.edit.pick": "Usar carta seleccionada",
        "decks.edit.no_selection": "Selecciona una carta de los resultados.",
        "decks.edit.over_target": "El total del listado no puede superar el tamaño original.",
        "optimize.target": "Mazo a armar",
        "optimize.run": "Calcular plan óptimo",
        "optimize.no_solutions": "No hay plan viable de desmontaje.",
        "optimize.already_armed": "Este mazo ya está armado — no hay nada que optimizar.",
        "optimize.multiple": "Hay varios planes óptimos — elige uno:",
        "optimize.from_inventory": "Cartas cubiertas por inventario libre",
        "optimize.decks_to_dismantle": "Mazos a desarmar",
        "optimize.missing": "Aún faltan",
        "optimize.unit.cards": "cartas",
        "optimize.unit.decks": "mazos",
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
        "browse.section.availability": "Disponibilidad",
        "browse.section.scryfall": "Scryfall",
        "browse.overview.greeting": (
            " __  __  _______   _____          _____\n"
            "|  \\/  ||__   __| / ____|        / ____|\n"
            "| \\  / |   | |   | |  __ ______ | (___\n"
            "| |\\/| |   | |   | | |_ |______| \\___ \\\n"
            "| |  | |   | |   | |__| |       ____) |\n"
            "|_|  |_|   |_|    \\_____|      |_____/"
        ),
        "browse.overview.tagline": "Gestor de Colección Commander",
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
        "browse.cards.flag.basic": "básica",
        "browse.cards.flag.token": "token",
        "browse.decks.quantity": "Cant.",
        "browse.decks.role": "Rol",
        "browse.inventory.copy": "Copia #",
        "browse.inventory.copies": "Copias",
        "browse.inventory.mixed": "{free} libres · {decks}",
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
