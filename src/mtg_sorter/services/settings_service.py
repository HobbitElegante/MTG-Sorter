from sqlalchemy.orm import Session

from mtg_sorter.config import DEFAULT_LOCALE, SETTING_UI_LOCALE
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
