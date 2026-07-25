from sqlalchemy.orm import Session

from mtg_sorter.models import AppSetting


class SettingsRepository:
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
