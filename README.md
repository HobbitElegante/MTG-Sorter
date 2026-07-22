# MTG Commander Collection Manager

Desktop application to manage a physical Magic: The Gathering Commander collection and compute optimal deck reassembly plans using integer linear programming (OR-Tools).

## Features (v0.3.4)

- Local SQLite inventory of physical card copies (grouped by card: total / free / assigned)
- Moxfield text import (`Copy for MTGO` format) with armed/dismantled flow and −/+ quantity steppers
- Deck list storage with armed/dismantled status and automatic copy assignment
- Table-based deck list editing (adjust quantities, free copies, replace/add cards within list size)
- Delete deck with optional removal of physical copies
- Commander roles: commander, partner, companion, background
- Unlimited basics and tokens (never block reassembly; flagged in Browse → Cards)
- ILP optimizer to minimize the number of armed decks to dismantle (readable card/deck names)
- Optimize section titles show counts (free coverage, decks to dismantle, still missing)
- Already-armed target decks skip optimization with a clear message
- Bilingual UI (English default, Spanish in Browse → Overview; locale persisted)
- **Browse tab:** overview, cached card catalog, availability search, Scryfall bulk sync
- **Inventory tab:** searchable collection table
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

43 tests passing.

## First-time setup

1. Run the app.
2. **Browse → Scryfall → Download oracle-cards bulk pack** (one-time, ~170 MB, requires network).
3. Import decks from the **Decks** tab.
4. Optional: **Browse → Overview** → switch language to Spanish (persisted).

## Importing a deck

1. Open the **Decks** tab → **Import Moxfield list**.
2. Enter deck name and optional commander name.
3. Paste the list or click **Load file** to open a `.txt` export.
4. Click **Confirm list**.
5. Choose **Armed** or **Dismantled**:
   - **Armed:** physical copies are created/assigned automatically. Shared cards across armed decks get additional copies.
   - **Dismantled:** mark which cards from the list you still have available (−/+) → free inventory copies.

Export from Moxfield: `More → Export → Copy for MTGO`.

## Editing and deleting decks

- **Edit list:** table of cards with list quantity, free inventory (−/+), replace, and add cards into open slots (list size preserved).
- **Delete list:** choose how many removable copies to drop per card; copies on other armed decks are never removed.
- Selected deck summary: dismantled shows free coverage toward reassembly; armed shows “complete”.

## Optimizer

1. Import decks and mark currently assembled ones as **Armed**.
2. For dismantled decks, register available copies during import or while editing.
3. Open **Optimize**, pick a **dismantled** target deck, and run the plan.
4. Section titles show counts: free inventory coverage, decks to dismantle, and still-missing cards.
5. If the target is already **Armed**, optimization is skipped (“already armed”).
6. If multiple optimal dismantle sets exist, choose one from the dropdown.

## Offline Scryfall cache

1. Open **Browse → Scryfall**.
2. Click **Download oracle-cards bulk pack**.
3. After sync, imports and lookups work offline for cached cards.
4. Individual API lookups are also saved automatically when online.

## Project layout

```
src/mtg_sorter/
  algorithms/   # ILP deck dismantle optimizer, card helpers
  api/          # Scryfall HTTP client
  database/     # SQLite session bootstrap
  i18n/         # EN/ES translations
  models/       # SQLAlchemy models
  services/     # Business logic
  ui/           # PySide6 desktop UI
tests/
  fixtures/     # Sample deck exports (e.g. kellan_deck.txt)
```

## Seed decks (reference)

Local DB typically includes armed seeds (Kellan, Athreos, Ghen, Legolas, Lord Xander) plus dismantled test decks (e.g. Emmara, Saskia).

Fixture: `tests/fixtures/kellan_deck.txt`

## Continuity

See [`handoff.md`](handoff.md) for full project state, decisions, and next steps.
