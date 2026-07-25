# MTG Commander Collection Manager

Desktop application to manage a physical Magic: The Gathering Commander collection and compute optimal deck reassembly plans using integer linear programming (OR-Tools).

## Features (v0.8.0)

### Collection

- Physical inventory in SQLite, grouped by card: total / free / assigned
- Inventory table: Name · Colors (WUBRG) · Total · Free · Assigned · In decks; sortable columns; search
- Add a single card or paste a whole list (multi-format / Moxfield URL) into free inventory
- Optional **edition tracking**: turn it on in Browse → Overview to get an Edition column, per-copy set codes, and a prompt after rebuilding a deck
- Card image preview beside the table (on-demand download; flip for double-faced cards)

### Decks

- Import with auto-detect: Moxfield MTGO, Archidekt, Arena, MTGO `.dek`, or public Moxfield URL
- Armed / dismantled status with automatic physical-copy assignment
- Command zone: commander plus optional Partner / Companion / Background
- Edit list (fixed size), **Update list** (replace from paste/file/URL with diff preview), export (5 formats), delete
- Search, filter by status, and reorder decks
- Advisory ⚠ that never blocks: Scryfall Commander legality plus game-rule checks (color identity, Partner / Background / Companion pairings, singleton with printed exceptions, 100-card list size)
- Lock / unlock a deck so Optimize will not dismantle it (🔒 in the list)

### Optimize

- ILP plan: minimize how many **armed** decks to dismantle to assemble a target
- **Assembly sequence:** add dismantled targets one by one; each step shows whether the plan is viable (or which cards are still missing), simulating earlier confirms
- **Locked decks** (Decks tab, 🔒): Optimize will not dismantle them; cards they hold still appear under Still missing
- Equally optimal plans are ordered so the one drawing the most cards from a single donor comes first; every plan stays selectable
- Confirm / cancel to apply; searchable target picker; clear status when already armed or infeasible
- Free inventory + unlimited basics count toward coverage; tokens are ignored (not stored on lists)

### Browse & data

- Offline card cache via Scryfall bulk (`oracle_cards` / optional `unique_artwork`); Art Series excluded
- Local JPEGs under `data/images/`; refresh legality + image URLs for the collection without a full re-bulk
- Browse: card search, availability, activity **History** (filter, load more, CSV, undo last)
- UI in English or Spanish (persisted)

## Download

Prebuilt binaries: **https://github.com/HobbitElegante/MTG-Sorter/releases/latest**

- Linux: `.AppImage` — `chmod +x` then run.
- Windows: `.zip` — unzip and run `MTG-Sorter.exe`.

Local development setup is below.

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

In development, the SQLite database is created at `data/mtg_sorter.db` (gitignored) and optional card images under `data/images/`. Packaged builds (AppImage / Windows folder) store the same files in the platform user-data directory; override anytime with `MTG_SORTER_DATA_DIR`. On every launch, Alembic applies any pending schema migrations automatically (fresh clone → baseline schema; older local DBs → one-time bridge + stamp).

## Tests

```bash
uv run pytest
```

187 tests passing.

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

## Editing, updating, exporting, and deleting decks

- **Edit list:** table of cards with list quantity, free inventory (−/+), replace, and add cards into open slots (list size preserved). Cards that are banned / not legal / restricted in Commander show ⚠ on the right of the Name column (tooltip; advisory only).
- **Update list:** opens the full-tab panel bound to the selected deck (name locked, command zone prefilled). Paste a list, load a file, or paste a Moxfield URL, then **Review update** shows cards to add / remove, the new card count, and any unrecognized lines (those are left out of the list). **Apply update** replaces the stored list — use this when the deck changed on Moxfield or an older import came in incomplete; the card count can grow or shrink. Armed decks are re-armed automatically (copies are created for cards new to the list).
- **Edit name / commander:** rename the deck; set or clear the commander; use **+** to add Partner, Companion, or Background (second card field). Cards must be in the local Scryfall cache.
- **Export list:** opens a dialog with a format picker (MTGO / Moxfield / Arena / Archidekt / MTGGoldfish); copy to clipboard.
- **Delete list:** choose how many removable copies to drop per card; copies on other armed decks are never removed.
- **Filter / reorder:** search by deck or commander name; show All, Armed only, or Dismantled only (compact dropdown); Move up / Move down persists custom order (reorder does not refresh Inventory/Browse).
- Selected deck summary: dismantled shows free coverage as `{available}/{needed}` trackable cards (basics/tokens excluded from the denominator); armed shows “complete”; commander and secondary role are shown when set. Decks with format-legality issues show ⚠ left of `[Armed|Dismantled]` (hover for the card list).

Tip: **Edit list** keeps the list size fixed (open slots only). To add or remove cards beyond that — or to fully replace the list from Moxfield — use **Update list**.

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

1. Import decks and mark currently assembled ones as **Armed**. Optionally **Lock** decks you never want Optimize to dismantle.
2. For dismantled decks, register available copies during import or while editing.
3. Open **Optimize**, search a dismantled deck, and click **Add to plan** (repeat to build a sequence).
4. The sequence list shows whether each step is viable or still missing cards (later steps assume earlier ones were confirmed).
5. Select a step to see free inventory, decks to dismantle, or Still missing / Need to find — same detail panels as a single plan.
6. **Confirm plan** applies the selected viable step; **Cancel** clears the whole sequence.
7. If multiple optimal dismantle sets exist for a step, choose one from the dropdown before confirming.

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
  algorithms/     # ILP deck dismantle optimizer, card helpers (incl. legality)
  api/            # Scryfall + Moxfield HTTP clients (bulk + CDN image download)
  database/       # SQLite + Alembic (session, migrate, alembic/versions)
  i18n/           # EN/ES translations
  models/         # SQLAlchemy models (ActivityEvent, Card.commander_legality/image_uri_back, …)
  repositories/   # Thin data-access layer (Card, Copy, Deck, Activity, Settings)
  services/       # Business logic / orchestration (uses repositories for SQL)
  ui/             # PySide6 desktop UI (+ inventory_display, card_preview, import/update dialogs)
tests/
  fixtures/       # Sample exports (kellan, arena, archidekt, mtgo .dek)
alembic.ini       # Dev CLI for new revisions (`alembic -c alembic.ini …`)
```

**Changing the schema:** add a revision with `alembic -c alembic.ini revision --autogenerate -m "…"`, review it under `database/alembic/versions/`, then launch the app (migrations run on startup).

## Latest (v0.8.0)

Commander rule warnings cover **singleton** (basics, “any number of cards named…”, and “up to N” caps like Seven Dwarves) and **list size** (100 cards; Companion outside). Decks can be **locked** (🔒) so Optimize will not dismantle them. Optimize builds an **assembly sequence**: add targets one by one, each with its own viability / missing-cards panel, simulating prior steps. The target picker looks like a committed selection (not free text) once a deck is chosen; clear resets the field. See also edition tracking and Optimize concentration tie-break from v0.7.0.
