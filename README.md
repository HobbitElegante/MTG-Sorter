# MTG Commander Collection Manager

Desktop application to manage a physical Magic: The Gathering Commander collection and compute optimal deck reassembly plans using integer linear programming (OR-Tools).

## Features (v0.5.0)

- Local SQLite inventory of physical card copies (grouped by card: total / free / assigned)
- **Card images in the UI:** preview panel beside Browse → Cards, Inventory, the deck list (commander plus partner/companion/background), Edit list, and the card pickers. Images come from the local cache and are downloaded on demand when missing; double-faced cards get a **Flip card** button. Toggle with **Browse → Overview → Show card images** (persisted); drag the splitter to resize
- **Inventory tab:** searchable table with columns Name · Colors · Total · Free · Assigned · In decks; click headers to sort (text A–Z, numbers high→low first); Name column stretched; add/edit copy counts (cannot drop below assigned copies)
- **Add list to collection:** full-tab paste/load (Moxfield / Archidekt / Arena / MTGO `.dek` / Moxfield URL) → review identified cards (qty from 1, remove/replace) with unresolved lines on the right (edit + recheck, or remove); confirm adds free copies
- **Deck import:** auto-detect format — Moxfield MTGO text, Archidekt, Arena (`Commander`/`Deck` sections), MTGO `.dek` XML, or paste a public Moxfield deck URL (fetched, then review); armed/dismantled flow with −/+ quantity steppers; strips set codes including The List (`SOI-51`, `115a`, …)
- **Import new list** takes the full Decks tab (deck list hidden while importing); optional Partner / Companion / Background via `+` (same as edit details)
- **Export list** to MTGO text (dialog + copy to clipboard)
- Deck list storage with armed/dismantled status and automatic copy assignment
- **Edit name / commander**, optional Partner / Companion / Background via `+`, filter All / Armed / Dismantled (compact), **search decks by name or commander**, reorder with Move up / Move down
- Deck actions: Edit list · Edit name / commander · Export · Delete (left); Mark armed / dismantled (right)
- Table-based deck list editing (adjust quantities, free copies, replace/add cards within list size)
- Delete deck with optional removal of physical copies
- Commander roles: commander, partner, companion, background
- **Commander legality warnings (advisory):** Scryfall `legalities.commander` is cached locally; decks with banned / not legal / restricted cards show ⚠ left of Armed/Dismantled (tooltip lists them). Edit list shows ⚠ flush-right in the Name column. Never blocks import or arming. **Browse → Scryfall → Refresh card data** updates legalities and image links for owned/list cards without a full bulk download.
- Unlimited basics and tokens (never block reassembly; flagged in Browse → Cards)
- Card lookup prefers the playable card when a token shares the same name (e.g. Darkstar Augur)
- ILP optimizer to minimize the number of armed decks to dismantle (readable card/deck names)
- **Optimize target:** searchable dropdown — type deck or commander name (`Name — Commander`)
- Optimize section titles show counts (free coverage, decks to dismantle, still missing)
- Already-armed target decks skip optimization with a clear message
- **Optimize plan UX:** large centered status (armed / no path / N decks); expanded **Decks to dismantle** tree with per-deck cards; Confirm / Cancel to apply dismantle+arm; **Cards covered by free inventory** also lists basic lands to pull from the unlimited pool (tokens still omitted)
- **Still missing (infeasible):** tree grouped by armed deck that holds the card; remainder under **Need to find** / **Faltan por encontrar**
- Bilingual UI (English default, Spanish in Browse → Overview; locale persisted)
- **Browse tab:** overview (language + show-images toggle), card search (type to search — does not dump the full ~36k cache), availability (same columns as Inventory minus Colors), **History** (append-only activity log: inventory + decks; filter All / Inventory / Decks), Scryfall bulk sync (oracle-cards / unique-artwork) + local image download + **Refresh card data (collection)**
- Lightweight UI refresh after collection changes (avoids rebuilding the full card catalog)
- Offline card resolution via local cache + Scryfall bulk packs (`oracle_cards` / optional `unique_artwork`)
- **Local card images:** Browse → Scryfall can download Scryfall `normal` JPEGs for the collection or full cache (`data/images/`); back faces are saved as `{oracle_id}_back.jpg`
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

The SQLite database is created at `data/mtg_sorter.db` (gitignored). Optional card images go under `data/images/` (also gitignored).

## Tests

```bash
uv run pytest
```

114 tests passing.

## First-time setup

1. Run the app.
2. **Browse → Scryfall → Download oracle-cards bulk pack** (one-time, ~170 MB, requires network).
3. Optional: **Use unique-artwork** for better default art; **Download images (collection)** for local JPEGs of owned/list cards.
4. Import decks from the **Decks** tab (**Import new list**).
5. Optional: **Browse → Overview** → switch language to Spanish, or uncheck **Show card images** (both persisted).

## Importing a deck

1. Open the **Decks** tab → **Import new list** (form fills the whole tab).
2. Enter deck name and optional commander; use **+** for Partner, Companion, or Background if needed (a Moxfield URL can fill these for you).
3. Paste the list, a public **Moxfield deck URL**, or click **Load file** (`.txt` / `.dek`).
4. Click **Confirm list**. If you pasted a Moxfield URL, the app downloads the deck, fills the form, and asks you to confirm again after review.
5. Choose **Armed** or **Dismantled**:
   - **Armed:** physical copies are created/assigned automatically. Shared cards across armed decks get additional copies.
   - **Dismantled:** mark which cards from the list you still have available (−/+) → free inventory copies.

Supported paste formats (auto-detected): Moxfield `Copy for MTGO`, Archidekt text, MTG Arena (`Commander` / `Deck` sections), MTGO `.dek` XML.

Export from Moxfield: `More → Export → Copy for MTGO` (or paste the deck URL).

## Editing, exporting, and deleting decks

- **Edit list:** table of cards with list quantity, free inventory (−/+), replace, and add cards into open slots (list size preserved). Cards that are banned / not legal / restricted in Commander show ⚠ on the right of the Name column (tooltip; advisory only).
- **Edit name / commander:** rename the deck; set or clear the commander; use **+** to add Partner, Companion, or Background (second card field). Cards must be in the local Scryfall cache.
- **Export list:** opens a dialog with the MTGO-format list; copy to clipboard for Moxfield or other tools.
- **Delete list:** choose how many removable copies to drop per card; copies on other armed decks are never removed.
- **Filter / reorder:** search by deck or commander name; show All, Armed only, or Dismantled only (compact dropdown); Move up / Move down persists custom order (reorder does not refresh Inventory/Browse).
- Selected deck summary: dismantled shows free coverage as `{available}/{needed}` trackable cards (basics/tokens excluded from the denominator); armed shows “complete”; commander and secondary role are shown when set. Decks with format-legality issues show ⚠ left of `[Armed|Dismantled]` (hover for the card list).

## Inventory

1. Open the **Inventory** tab.
2. Table columns: **Name** · **Colors** · **Total** · **Free** · **Assigned** · **In decks** (deck names only, or — if fully free). Colors show WUBRG identity (— if colorless). Name is the wide column.
3. Click a column header to sort (text A–Z / Z–A; numbers high→low first, then reverse). Hover **In decks** for the full list when a card is in several decks.
4. Use the search bar to filter your collection.
5. **Add new card to collection** — search the local Scryfall cache and add free copies (−/+). Basics and tokens are excluded (unlimited / not trackable).
6. **Add list to collection** — opens a full-tab paste area (Load file · Confirm list · Cancel). After confirm, adjust how many copies to add per identified card (starts at 1; 0 or Remove excludes), replace mis-resolved cards, and on the right edit unrecognized lines then **Recheck** or **Remove** them. Confirm adds free inventory copies.
7. Select a row → **Edit copy count** — change total physical copies (floor = copies assigned to armed decks).
8. The panel on the right shows the selected card. Missing images are fetched from Scryfall in the background and cached; drag the splitter to resize it.

## Optimizer

1. Import decks and mark currently assembled ones as **Armed**.
2. For dismantled decks, register available copies during import or while editing.
3. Open **Optimize**, pick a **dismantled** target deck (type to filter by deck or commander name), and run the plan.
4. A large centered status shows the outcome (already armed, no viable path, inventory-only, or how many decks to dismantle).
5. **Cards covered by free inventory** lists free copies used (compact), plus basic lands to take from the unlimited pool. **Decks to dismantle** is the main panel: tree of donor decks with the cards each contributes toward the target.
6. **Still missing** appears only when the plan is infeasible. Cards still held by armed decks are grouped under those deck names; anything not in free inventory or any armed deck is listed under **Need to find**.
7. **Confirm plan** dismantles the chosen armed decks and arms the target; **Cancel** clears the plan without changing the database.
8. If multiple optimal dismantle sets exist, choose one from the dropdown before confirming.

## Offline Scryfall cache

1. Open **Browse → Scryfall**.
2. Click **Download oracle-cards bulk pack** (one-time, ~170 MB) for offline name resolution. When Scryfall publishes newer data, the button becomes **Update**.
3. Optional: **Use unique-artwork** (~250 MB) for better default card art (still one row per `oracle_id`).
4. Optional: **Download images (collection)** or **Download images (full cache)** — saves Scryfall `normal` JPEGs under `data/images/{oracle_id}.jpg` (skips files already on disk). Bulk download only fetches front faces; back faces arrive on demand when you flip a card.
5. After sync, imports and lookups work offline for cached cards.
6. Individual API lookups are also saved automatically when online.
7. **Refresh card data (collection)** — updates Commander legality and image links for cards you own or have on deck lists (batched Scryfall API; much faster than a full bulk re-download). Use this when banlists change, or after upgrading so ⚠ warnings and back-face images work.
8. **Browse → Cards:** type a name to search; the UI does not load the entire cached catalog at once. Selecting a row shows the card image on the right.

## Project layout

```
src/mtg_sorter/
  algorithms/   # ILP deck dismantle optimizer, card helpers (incl. legality)
  api/          # Scryfall + Moxfield HTTP clients (bulk + CDN image download)
  database/     # SQLite session bootstrap (+ column migrates)
  i18n/         # EN/ES translations
  models/       # SQLAlchemy models (ActivityEvent, Card.commander_legality/image_uri_back, …)
  services/     # Business logic (activity, bulk sync, card images, import, …)
  ui/           # PySide6 desktop UI (+ inventory_display helpers, card_preview panel)
tests/
  fixtures/     # Sample exports (kellan, arena, archidekt, mtgo .dek)
```

## Continuity

See [`handoff.md`](handoff.md) for full project state (**v0.5.0**, session closed 2026-07-24).

**Done (v0.5.0):** card image previews across Browse → Cards, Inventory, deck detail, Edit list and the card pickers; on-demand download with an LRU pixmap cache; persisted show/hide toggle and splitter width; `Card.image_uri_back` plus a **Flip card** button for double-faced cards.

**Next recommended:** backlog — Commander game rules validation, tokens in Optimize, multi-format export, packaging, Alembic.

Note: `handoff.md` is gitignored (local continuity); README is the tracked summary.
