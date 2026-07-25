from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "mtg_sorter.db"
IMAGES_DIR = DATA_DIR / "images"
SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_RATE_LIMIT_SECONDS = 0.1
SCRYFALL_BULK_ORACLE_TYPE = "oracle_cards"
SCRYFALL_BULK_UNIQUE_ARTWORK_TYPE = "unique_artwork"
SCRYFALL_BULK_TYPES = frozenset(
    {SCRYFALL_BULK_ORACLE_TYPE, SCRYFALL_BULK_UNIQUE_ARTWORK_TYPE}
)
SCRYFALL_BULK_BATCH_SIZE = 500
SCRYFALL_COLLECTION_BATCH_SIZE = 75
MOXFIELD_API_BASE = "https://api2.moxfield.com"
DEFAULT_LOCALE = "en"

SETTING_UI_LOCALE = "ui_locale"
SETTING_SHOW_CARD_IMAGES = "ui_show_card_images"
SETTING_TRACK_EDITIONS = "ui_track_editions"
SETTING_CARD_PREVIEW_WIDTH = "ui_card_preview_width"
UNSPECIFIED_EDITION_LABEL = "-"
DEFAULT_CARD_PREVIEW_WIDTH = 280
SETTING_BULK_PACK_TYPE = "scryfall_bulk_pack_type"
SETTING_BULK_ORACLE_UPDATED_AT = "scryfall_bulk_oracle_updated_at"
SETTING_BULK_ORACLE_SYNCED_AT = "scryfall_bulk_oracle_synced_at"
SETTING_BULK_ORACLE_CARD_COUNT = "scryfall_bulk_oracle_card_count"
