from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "mtg_sorter.db"
SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_RATE_LIMIT_SECONDS = 0.1
DEFAULT_LOCALE = "en"
