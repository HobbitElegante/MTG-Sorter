from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_rebuilder.config import (
    DEFAULT_CARD_PREVIEW_WIDTH,
    DEFAULT_LOCALE,
    DEFAULT_UI_THEME,
    SETTING_CARD_PREVIEW_WIDTH,
    SETTING_UI_LOCALE,
    SETTING_UI_THEME,
    SETTING_WINDOW_GEOMETRY,
    THEME_DARK,
)
from mtg_rebuilder.models import Base
from mtg_rebuilder.services.settings_service import SettingsService


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


def test_get_ui_theme_defaults_when_missing(session: Session) -> None:
    assert SettingsService(session).get_ui_theme() == DEFAULT_UI_THEME


def test_set_and_get_ui_theme(session: Session) -> None:
    settings = SettingsService(session)

    settings.set_ui_theme(THEME_DARK)

    assert settings.get(SETTING_UI_THEME) == THEME_DARK
    assert settings.get_ui_theme() == THEME_DARK


def test_get_ui_theme_falls_back_on_invalid_value(session: Session) -> None:
    settings = SettingsService(session)
    settings.set(SETTING_UI_THEME, "neon")

    assert settings.get_ui_theme() == DEFAULT_UI_THEME


def test_set_ui_theme_rejects_unsupported(session: Session) -> None:
    with pytest.raises(ValueError, match="Unsupported theme"):
        SettingsService(session).set_ui_theme("neon")


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


def test_window_geometry_round_trip(session: Session) -> None:
    settings = SettingsService(session)
    assert settings.get_window_geometry() is None

    settings.set_window_geometry("YWJjZA==")
    assert settings.get_window_geometry() == "YWJjZA=="

    settings.set(SETTING_WINDOW_GEOMETRY, "   ")
    assert settings.get_window_geometry() is None


def test_legality_and_rule_warnings_default_on(session: Session) -> None:
    settings = SettingsService(session)
    assert settings.get_show_legality_warnings() is True
    assert settings.get_show_rule_warnings() is True

    settings.set_show_legality_warnings(False)
    settings.set_show_rule_warnings(False)
    assert settings.get_show_legality_warnings() is False
    assert settings.get_show_rule_warnings() is False

    settings.set_show_legality_warnings(True)
    settings.set_show_rule_warnings(True)
    assert settings.get_show_legality_warnings() is True
    assert settings.get_show_rule_warnings() is True
