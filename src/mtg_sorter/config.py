from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "mtg_sorter.db"
SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_RATE_LIMIT_SECONDS = 0.1
SCRYFALL_BULK_ORACLE_TYPE = "oracle_cards"
SCRYFALL_BULK_BATCH_SIZE = 500
SCRYFALL_COLLECTION_BATCH_SIZE = 75
MOXFIELD_API_BASE = "https://api2.moxfield.com"
DEFAULT_LOCALE = "en"

SETTING_UI_LOCALE = "ui_locale"
SETTING_BULK_ORACLE_UPDATED_AT = "scryfall_bulk_oracle_updated_at"
SETTING_BULK_ORACLE_SYNCED_AT = "scryfall_bulk_oracle_synced_at"
SETTING_BULK_ORACLE_CARD_COUNT = "scryfall_bulk_oracle_card_count"
