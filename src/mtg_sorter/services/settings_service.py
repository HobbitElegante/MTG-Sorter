from sqlalchemy.orm import Session

from mtg_sorter.config import (
    DEFAULT_CARD_PREVIEW_WIDTH,
    DEFAULT_LOCALE,
    DEFAULT_UI_THEME,
    SETTING_CARD_PREVIEW_WIDTH,
    SETTING_SHOW_CARD_IMAGES,
    SETTING_SHOW_LEGALITY_WARNINGS,
    SETTING_SHOW_RULE_WARNINGS,
    SETTING_TRACK_EDITIONS,
    SETTING_UI_LOCALE,
    SETTING_UI_THEME,
    SETTING_WINDOW_GEOMETRY,
    UI_THEMES,
)
from mtg_sorter.i18n.translator import TRANSLATIONS
from mtg_sorter.repositories import SettingsRepository


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = SettingsRepository(session)

    def get(self, key: str) -> str | None:
        return self._settings.get(key)

    def set(self, key: str, value: str) -> None:
        self._settings.set(key, value)

    def get_ui_locale(self) -> str:
        locale = self.get(SETTING_UI_LOCALE)
        if locale in TRANSLATIONS:
            return locale
        return DEFAULT_LOCALE

    def set_ui_locale(self, locale: str) -> None:
        if locale not in TRANSLATIONS:
            raise ValueError(f"Unsupported locale: {locale}")
        self.set(SETTING_UI_LOCALE, locale)

    def get_ui_theme(self) -> str:
        theme = self.get(SETTING_UI_THEME)
        if theme in UI_THEMES:
            return theme
        return DEFAULT_UI_THEME

    def set_ui_theme(self, theme: str) -> None:
        if theme not in UI_THEMES:
            raise ValueError(f"Unsupported theme: {theme}")
        self.set(SETTING_UI_THEME, theme)

    def get_show_card_images(self) -> bool:
        value = self.get(SETTING_SHOW_CARD_IMAGES)
        if value is None:
            return True
        return value == "1"

    def set_show_card_images(self, enabled: bool) -> None:
        self.set(SETTING_SHOW_CARD_IMAGES, "1" if enabled else "0")

    def get_track_editions(self) -> bool:
        """Off by default: existing collections have no per-copy edition data."""
        return self.get(SETTING_TRACK_EDITIONS) == "1"

    def set_track_editions(self, enabled: bool) -> None:
        self.set(SETTING_TRACK_EDITIONS, "1" if enabled else "0")

    def get_show_legality_warnings(self) -> bool:
        value = self.get(SETTING_SHOW_LEGALITY_WARNINGS)
        if value is None:
            return True
        return value == "1"

    def set_show_legality_warnings(self, enabled: bool) -> None:
        self.set(SETTING_SHOW_LEGALITY_WARNINGS, "1" if enabled else "0")

    def get_show_rule_warnings(self) -> bool:
        value = self.get(SETTING_SHOW_RULE_WARNINGS)
        if value is None:
            return True
        return value == "1"

    def set_show_rule_warnings(self, enabled: bool) -> None:
        self.set(SETTING_SHOW_RULE_WARNINGS, "1" if enabled else "0")

    def get_card_preview_width(self) -> int:
        value = self.get(SETTING_CARD_PREVIEW_WIDTH)
        try:
            width = int(value) if value is not None else DEFAULT_CARD_PREVIEW_WIDTH
        except ValueError:
            return DEFAULT_CARD_PREVIEW_WIDTH
        return width if width > 0 else DEFAULT_CARD_PREVIEW_WIDTH

    def set_card_preview_width(self, width: int) -> None:
        if width > 0:
            self.set(SETTING_CARD_PREVIEW_WIDTH, str(width))

    def get_window_geometry(self) -> str | None:
        value = self.get(SETTING_WINDOW_GEOMETRY)
        if value is None or not value.strip():
            return None
        return value

    def set_window_geometry(self, geometry: str) -> None:
        if geometry:
            self.set(SETTING_WINDOW_GEOMETRY, geometry)
