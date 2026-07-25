from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.config import (
    DEFAULT_CARD_PREVIEW_WIDTH,
    DEFAULT_LOCALE,
    SETTING_CARD_PREVIEW_WIDTH,
    SETTING_UI_LOCALE,
)
from mtg_sorter.models import Base
from mtg_sorter.services.settings_service import SettingsService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_get_ui_locale_defaults_when_missing(session: Session) -> None:
    assert SettingsService(session).get_ui_locale() == DEFAULT_LOCALE


def test_set_and_get_ui_locale(session: Session) -> None:
    settings = SettingsService(session)

    settings.set_ui_locale("es")

    assert settings.get(SETTING_UI_LOCALE) == "es"
    assert settings.get_ui_locale() == "es"


def test_get_ui_locale_falls_back_on_invalid_value(session: Session) -> None:
    settings = SettingsService(session)
    settings.set(SETTING_UI_LOCALE, "fr")

    assert settings.get_ui_locale() == DEFAULT_LOCALE


def test_set_ui_locale_rejects_unsupported(session: Session) -> None:
    with pytest.raises(ValueError, match="Unsupported locale"):
        SettingsService(session).set_ui_locale("fr")


def test_show_card_images_defaults_to_enabled(session: Session) -> None:
    assert SettingsService(session).get_show_card_images() is True


def test_set_and_get_show_card_images(session: Session) -> None:
    settings = SettingsService(session)

    settings.set_show_card_images(False)
    assert settings.get_show_card_images() is False

    settings.set_show_card_images(True)
    assert settings.get_show_card_images() is True


def test_card_preview_width_defaults_and_rejects_garbage(session: Session) -> None:
    settings = SettingsService(session)
    assert settings.get_card_preview_width() == DEFAULT_CARD_PREVIEW_WIDTH

    settings.set(SETTING_CARD_PREVIEW_WIDTH, "not-a-number")
    assert settings.get_card_preview_width() == DEFAULT_CARD_PREVIEW_WIDTH

    settings.set_card_preview_width(320)
    assert settings.get_card_preview_width() == 320
