from sqlalchemy.orm import Session

from mtg_sorter.config import (
    DEFAULT_CARD_PREVIEW_WIDTH,
    DEFAULT_LOCALE,
    SETTING_CARD_PREVIEW_WIDTH,
    SETTING_SHOW_CARD_IMAGES,
    SETTING_UI_LOCALE,
)
from mtg_sorter.i18n.translator import TRANSLATIONS
from mtg_sorter.models import AppSetting


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> str | None:
        setting = self._session.get(AppSetting, key)
        return setting.value if setting is not None else None

    def set(self, key: str, value: str) -> None:
        setting = self._session.get(AppSetting, key)
        if setting is None:
            self._session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
        self._session.flush()

    def get_ui_locale(self) -> str:
        locale = self.get(SETTING_UI_LOCALE)
        if locale in TRANSLATIONS:
            return locale
        return DEFAULT_LOCALE

    def set_ui_locale(self, locale: str) -> None:
        if locale not in TRANSLATIONS:
            raise ValueError(f"Unsupported locale: {locale}")
        self.set(SETTING_UI_LOCALE, locale)

    def get_show_card_images(self) -> bool:
        value = self.get(SETTING_SHOW_CARD_IMAGES)
        if value is None:
            return True
        return value == "1"

    def set_show_card_images(self, enabled: bool) -> None:
        self.set(SETTING_SHOW_CARD_IMAGES, "1" if enabled else "0")

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
