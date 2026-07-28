from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DATA_DIRNAME = "mtg-sorter"
ENV_DATA_DIR = "MTG_SORTER_DATA_DIR"

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    """True when running from a frozen bundle (e.g. PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def resource_root(
    *,
    frozen: bool | None = None,
    meipass: Path | None = None,
) -> Path:
    """Root for bundled assets.

    Frozen builds use PyInstaller's ``sys._MEIPASS``. In development this is the
    ``mtg_sorter`` package directory (``src/mtg_sorter``).
    """
    if frozen if frozen is not None else is_frozen():
        if meipass is not None:
            return Path(meipass)
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def alembic_script_location(
    *,
    frozen: bool | None = None,
    meipass: Path | None = None,
) -> Path:
    """Directory passed to Alembic as ``script_location``.

    Spec datas land at ``_MEIPASS/mtg_sorter/database/alembic``; in development
    the same relative path lives under the package.
    """
    if frozen if frozen is not None else is_frozen():
        return resource_root(frozen=True, meipass=meipass) / "mtg_sorter" / "database" / "alembic"
    return resource_root(frozen=False) / "database" / "alembic"


def default_user_data_dir(
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Platform user-data directory for packaged installs (not used in dev)."""
    env = os.environ if environ is None else environ
    home_path = Path.home() if home is None else home
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        base = env.get("LOCALAPPDATA")
        root = Path(base) if base else home_path / "AppData" / "Local"
        return root / APP_DATA_DIRNAME
    if plat == "darwin":
        return home_path / "Library" / "Application Support" / APP_DATA_DIRNAME
    xdg = env.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_DATA_DIRNAME
    return home_path / ".local" / "share" / APP_DATA_DIRNAME


def resolve_data_dir(
    *,
    environ: dict[str, str] | None = None,
    frozen: bool | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Resolve where SQLite + images live.

    Priority: ``MTG_SORTER_DATA_DIR`` → user data dir if frozen → ``<project>/data``.
    """
    env = os.environ if environ is None else environ
    override = (env.get(ENV_DATA_DIR) or "").strip()
    if override:
        return Path(override).expanduser()
    if frozen if frozen is not None else is_frozen():
        return default_user_data_dir(environ=env, home=home, platform=platform)
    root = PROJECT_ROOT if project_root is None else project_root
    return root / "data"


DATA_DIR = resolve_data_dir()
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
ARCHIDEKT_API_BASE = "https://archidekt.com"
DEFAULT_LOCALE = "en"

SETTING_UI_LOCALE = "ui_locale"
SETTING_SHOW_CARD_IMAGES = "ui_show_card_images"
SETTING_TRACK_EDITIONS = "ui_track_editions"
SETTING_SHOW_LEGALITY_WARNINGS = "ui_show_legality_warnings"
SETTING_SHOW_RULE_WARNINGS = "ui_show_rule_warnings"
SETTING_CARD_PREVIEW_WIDTH = "ui_card_preview_width"
SETTING_WINDOW_GEOMETRY = "ui_window_geometry"
HOUSE_BANNED_LEGALITY = "house_banned"
UNSPECIFIED_EDITION_LABEL = "-"
DEFAULT_CARD_PREVIEW_WIDTH = 280
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 1100
MIN_WINDOW_HEIGHT = 640
SETTING_BULK_PACK_TYPE = "scryfall_bulk_pack_type"
SETTING_BULK_ORACLE_UPDATED_AT = "scryfall_bulk_oracle_updated_at"
SETTING_BULK_ORACLE_SYNCED_AT = "scryfall_bulk_oracle_synced_at"
SETTING_BULK_ORACLE_CARD_COUNT = "scryfall_bulk_oracle_card_count"
