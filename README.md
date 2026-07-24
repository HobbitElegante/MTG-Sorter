# MTG Commander Collection Manager

Desktop application to manage a physical Magic: The Gathering Commander collection and compute optimal deck reassembly plans using integer linear programming (OR-Tools).

## Features (v0.3.14)

- Local SQLite inventory of physical card copies (grouped by card: total / free / assigned)
- **Inventory tab:** searchable table with columns Name · Total · Free · Assigned · In decks; click headers to sort (text A–Z, numbers high→low first); Name column stretched; add/edit copy counts (cannot drop below assigned copies)
- **Add list to collection:** full-tab paste/load MTGO text (no deck name fields) → review identified cards (qty from 1, remove/replace) with unresolved lines on the right (edit + recheck, or remove); confirm adds free copies
- Moxfield text import (`Copy for MTGO` format) with armed/dismantled flow and −/+ quantity steppers
- **Import new list** takes the full Decks tab (deck list hidden while importing)
- **Export list** to MTGO text (dialog + copy to clipboard)
- Deck list storage with armed/dismantled status and automatic copy assignment
- **Edit name / commander**, optional Partner / Companion / Background via `+`, filter All / Armed / Dismantled (compact), **search decks by name or commander**, reorder with Move up / Move down
- Deck actions: Edit list · Edit name / commander · Export · Delete (left); Mark armed / dismantled (right)
- Table-based deck list editing (adjust quantities, free copies, replace/add cards within list size)
- Delete deck with optional removal of physical copies
- Commander roles: commander, partner, companion, background
- Unlimited basics and tokens (never block reassembly; flagged in Browse → Cards)
- Card lookup prefers the playable card when a token shares the same name (e.g. Darkstar Augur)
- ILP optimizer to minimize the number of armed decks to dismantle (readable card/deck names)
- **Optimize target:** searchable dropdown — type deck or commander name (`Name — Commander`)
- Optimize section titles show counts (free coverage, decks to dismantle, still missing)
- Already-armed target decks skip optimization with a clear message
- **Optimize plan UX:** large centered status (armed / no path / N decks); expanded **Decks to dismantle** tree with per-deck cards; Confirm / Cancel to apply dismantle+arm
- Bilingual UI (English default, Spanish in Browse → Overview; locale persisted)
- **Browse tab:** overview, card search (type to search — does not dump the full ~36k cache), availability, Scryfall bulk sync
- Lightweight UI refresh after collection changes (avoids rebuilding the full card catalog)
- Offline card resolution via local cache + optional Scryfall `oracle-cards` bulk download
- Art Series cards filtered from bulk import and Browse catalog

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
cd MTG-Sorter
uv sync --all-extras
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uv run mtg-sorter
```

Or:

```bash
python -m mtg_sorter
```

The SQLite database is created at `data/mtg_sorter.db` (gitignored).

## Tests

```bash
uv run pytest
```

59 tests passing.

## First-time setup

1. Run the app.
2. **Browse → Scryfall → Download oracle-cards bulk pack** (one-time, ~170 MB, requires network).
3. Import decks from the **Decks** tab (**Import new list**).
4. Optional: **Browse → Overview** → switch language to Spanish (persisted).

## Importing a deck

1. Open the **Decks** tab → **Import new list** (form fills the whole tab).
2. Enter deck name and optional commander name.
3. Paste the list or click **Load file** to open a `.txt` export.
4. Click **Confirm list**.
5. Choose **Armed** or **Dismantled**:
   - **Armed:** physical copies are created/assigned automatically. Shared cards across armed decks get additional copies.
   - **Dismantled:** mark which cards from the list you still have available (−/+) → free inventory copies.

Export from Moxfield: `More → Export → Copy for MTGO`.

## Editing, exporting, and deleting decks

- **Edit list:** table of cards with list quantity, free inventory (−/+), replace, and add cards into open slots (list size preserved).
- **Edit name / commander:** rename the deck; set or clear the commander; use **+** to add Partner, Companion, or Background (second card field). Cards must be in the local Scryfall cache.
- **Export list:** opens a dialog with the MTGO-format list; copy to clipboard for Moxfield or other tools.
- **Delete list:** choose how many removable copies to drop per card; copies on other armed decks are never removed.
- **Filter / reorder:** search by deck or commander name; show All, Armed only, or Dismantled only (compact dropdown); Move up / Move down persists custom order (reorder does not refresh Inventory/Browse).
- Selected deck summary: dismantled shows free coverage toward reassembly; armed shows “complete”; commander and secondary role are shown when set.

## Inventory

1. Open the **Inventory** tab.
2. Table columns: **Name** · **Total** · **Free** · **Assigned** · **In decks** (deck names only, or — if fully free). Name is the wide column.
3. Click a column header to sort (text A–Z / Z–A; numbers high→low first, then reverse). Hover **In decks** for the full list when a card is in several decks.
4. Use the search bar to filter your collection.
5. **Add new card to collection** — search the local Scryfall cache and add free copies (−/+). Basics and tokens are excluded (unlimited / not trackable).
6. **Add list to collection** — opens a full-tab paste area (Load file · Confirm list · Cancel). After confirm, adjust how many copies to add per identified card (starts at 1; 0 or Remove excludes), replace mis-resolved cards, and on the right edit unrecognized lines then **Recheck** or **Remove** them. Confirm adds free inventory copies.
7. Select a row → **Edit copy count** — change total physical copies (floor = copies assigned to armed decks).

## Optimizer

1. Import decks and mark currently assembled ones as **Armed**.
2. For dismantled decks, register available copies during import or while editing.
3. Open **Optimize**, pick a **dismantled** target deck (type to filter by deck or commander name), and run the plan.
4. A large centered status shows the outcome (already armed, no viable path, inventory-only, or how many decks to dismantle).
5. **Cards covered by free inventory** lists free copies used (compact). **Decks to dismantle** is the main panel: tree of donor decks with the cards each contributes toward the target.
6. **Still missing** appears only when the plan is infeasible.
7. **Confirm plan** dismantles the chosen armed decks and arms the target; **Cancel** clears the plan without changing the database.
8. If multiple optimal dismantle sets exist, choose one from the dropdown before confirming.

## Offline Scryfall cache

1. Open **Browse → Scryfall**.
2. Click **Download oracle-cards bulk pack**.
3. After sync, imports and lookups work offline for cached cards.
4. Individual API lookups are also saved automatically when online.
5. **Browse → Cards:** type a name to search; the UI does not load the entire cached catalog at once.

## Project layout

```
src/mtg_sorter/
  algorithms/   # ILP deck dismantle optimizer, card helpers
  api/          # Scryfall HTTP client
  database/     # SQLite session bootstrap (+ sort_order migrate)
  i18n/         # EN/ES translations
  models/       # SQLAlchemy models
  services/     # Business logic
  ui/           # PySide6 desktop UI (+ inventory_display helpers)
tests/
  fixtures/     # Sample deck exports (e.g. kellan_deck.txt)
  # includes test_inventory_display.py, test_import_service preview cases
```

## Continuity

See [`handoff.md`](handoff.md) for full project state (v0.3.14), product decisions, architecture notes, and next steps.
