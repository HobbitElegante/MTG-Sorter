# MTG Commander Collection Manager

Desktop application to manage a physical Magic: The Gathering Commander collection and compute optimal deck reassembly plans using integer linear programming (OR-Tools).

## Features (v0.1)

- Local SQLite inventory of physical card copies
- Moxfield text import (`Copy for MTGO` format)
- Deck list storage with armed/dismantled status
- Commander roles: commander, partner, companion, background
- Unlimited basics and tokens (display only, never block reassembly)
- ILP optimizer to minimize the number of armed decks to dismantle
- Bilingual UI (English default, Spanish available)

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
cd MTG-Sorter
uv sync
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

## Importing a deck

1. Open the **Decks** tab.
2. Export from Moxfield: `More → Export → Copy for MTGO`.
3. Paste the list or load the `.txt` file.
4. Set deck name and optional commander name (e.g. `Kellan, the Kid`).
5. Mark armed decks with **Mark armed**.

## Optimizer

1. Add physical copies in **Inventory**.
2. Import decks and mark currently assembled ones as **Armed**.
3. Open **Optimize**, pick a dismantled target deck, and run the plan.
4. If multiple optimal dismantle sets exist, choose one from the dropdown.

## Project layout

```
src/mtg_sorter/
  algorithms/   # ILP deck dismantle optimizer
  api/          # Scryfall HTTP client
  database/     # SQLite session bootstrap
  models/       # SQLAlchemy models
  services/     # Business logic
  ui/           # PySide6 desktop UI
tests/
```

## Known armed decks (seed data reference)

- Kellan, the Top Decker Kid
- Lord Xander, today i'm kinda villain
- Legolas, 2 Arrows and a Dream
- Ghen, but i love giving poop as a gift

Fixture: `tests/fixtures/kellan_deck.txt`
