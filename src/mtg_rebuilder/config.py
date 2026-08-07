from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DATA_DIRNAME = "mtg-rebuilder"
LEGACY_APP_DATA_DIRNAME = "mtg-sorter"
ENV_DATA_DIR = "MTG_REBUILDER_DATA_DIR"
LEGACY_ENV_DATA_DIR = "MTG_SORTER_DATA_DIR"
DATABASE_FILENAME = "mtg_rebuilder.db"
LEGACY_DATABASE_FILENAME = "mtg_sorter.db"

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
    ``mtg_rebuilder`` package directory (``src/mtg_rebuilder``).
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

    Spec datas land at ``_MEIPASS/mtg_rebuilder/database/alembic``; in development
    the same relative path lives under the package.
    """
    if frozen if frozen is not None else is_frozen():
        return resource_root(frozen=True, meipass=meipass) / "mtg_rebuilder" / "database" / "alembic"
    return resource_root(frozen=False) / "database" / "alembic"


def _user_data_dir_for(
    dirname: str,
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    home_path = Path.home() if home is None else home
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        base = env.get("LOCALAPPDATA")
        root = Path(base) if base else home_path / "AppData" / "Local"
        return root / dirname
    if plat == "darwin":
        return home_path / "Library" / "Application Support" / dirname
    xdg = env.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / dirname
    return home_path / ".local" / "share" / dirname


def default_user_data_dir(
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Platform user-data directory for packaged installs (not used in dev)."""
    return _user_data_dir_for(
        APP_DATA_DIRNAME, environ=environ, home=home, platform=platform
    )


def migrate_legacy_user_data_dir(target: Path, legacy: Path) -> Path:
    """Rename legacy ``mtg-sorter`` user-data dir to ``mtg-rebuilder`` once."""
    if target.exists() or not legacy.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy.rename(target)
    return target


def migrate_legacy_database(data_dir: Path) -> Path:
    """Rename ``mtg_sorter.db`` → ``mtg_rebuilder.db`` inside ``data_dir`` if needed."""
    new_db = data_dir / DATABASE_FILENAME
    legacy_db = data_dir / LEGACY_DATABASE_FILENAME
    if new_db.exists() or not legacy_db.exists():
        return new_db
    legacy_db.rename(new_db)
    return new_db


def resolve_database_path(data_dir: Path | None = None) -> Path:
    """Database file path, migrating the legacy filename when present."""
    root = DATA_DIR if data_dir is None else data_dir
    return migrate_legacy_database(root)


def resolve_data_dir(
    *,
    environ: dict[str, str] | None = None,
    frozen: bool | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    platform: str | None = None,
    migrate_legacy: bool = True,
) -> Path:
    """Resolve where SQLite + images live.

    Priority: ``MTG_REBUILDER_DATA_DIR`` (or legacy ``MTG_SORTER_DATA_DIR``) →
    user data dir if frozen (with one-shot rename from ``mtg-sorter``) →
    ``<project>/data``.
    """
    env = os.environ if environ is None else environ
    override = (env.get(ENV_DATA_DIR) or env.get(LEGACY_ENV_DATA_DIR) or "").strip()
    if override:
        return Path(override).expanduser()
    if frozen if frozen is not None else is_frozen():
        target = default_user_data_dir(environ=env, home=home, platform=platform)
        if not migrate_legacy:
            return target
        legacy = _user_data_dir_for(
            LEGACY_APP_DATA_DIRNAME, environ=env, home=home, platform=platform
        )
        return migrate_legacy_user_data_dir(target, legacy)
    root = PROJECT_ROOT if project_root is None else project_root
    return root / "data"


DATA_DIR = resolve_data_dir()
DATABASE_PATH = resolve_database_path(DATA_DIR)
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

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"
UI_THEMES = frozenset({THEME_LIGHT, THEME_DARK, THEME_SYSTEM})
DEFAULT_UI_THEME = THEME_DARK

SETTING_UI_LOCALE = "ui_locale"
SETTING_UI_THEME = "ui_theme"
SETTING_SHOW_CARD_IMAGES = "ui_show_card_images"
SETTING_TRACK_EDITIONS = "ui_track_editions"
SETTING_SHOW_LEGALITY_WARNINGS = "ui_show_legality_warnings"
SETTING_SHOW_RULE_WARNINGS = "ui_show_rule_warnings"
SETTING_CARD_PREVIEW_WIDTH = "ui_card_preview_width"
SETTING_WINDOW_GEOMETRY = "ui_window_geometry"
SETTING_VIABLE_PLANS_CACHE = "viable_plans_cache"
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
