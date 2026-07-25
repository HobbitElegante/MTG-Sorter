from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from mtg_sorter.database import session as session_module


@pytest.fixture
def legacy_engine(tmp_path: Path):
    """A pre-v0.5.0 cards table, without image_uri_back."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE cards ("
                "oracle_id VARCHAR(36) PRIMARY KEY, "
                "name VARCHAR(255), "
                "image_uri VARCHAR(512))"
            )
        )
        conn.execute(
            text("INSERT INTO cards (oracle_id, name) VALUES ('a', 'Sol Ring')")
        )
    return engine


def _card_columns(engine) -> set[str]:
    with engine.begin() as conn:
        return {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(cards)")).fetchall()
        }


def test_migration_adds_image_uri_back(legacy_engine, monkeypatch) -> None:
    monkeypatch.setattr(session_module, "engine", legacy_engine)

    session_module._ensure_card_image_uri_back()

    assert "image_uri_back" in _card_columns(legacy_engine)
    with legacy_engine.begin() as conn:
        row = conn.execute(
            text("SELECT name, image_uri_back FROM cards WHERE oracle_id = 'a'")
        ).first()
    assert row == ("Sol Ring", None)


def test_migration_is_idempotent(legacy_engine, monkeypatch) -> None:
    monkeypatch.setattr(session_module, "engine", legacy_engine)

    session_module._ensure_card_image_uri_back()
    session_module._ensure_card_image_uri_back()

    assert "image_uri_back" in _card_columns(legacy_engine)
