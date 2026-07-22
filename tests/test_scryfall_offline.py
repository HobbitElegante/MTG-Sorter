import gzip
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mtg_sorter.models import AppSetting, Base, Card
from mtg_sorter.services.scryfall_bulk_service import (
    ScryfallBulkService,
    _iter_bulk_card_payloads,
)
from mtg_sorter.services.scryfall_service import (
    ScryfallOfflineError,
    ScryfallService,
    card_from_scryfall,
    normalize_card_name,
)


class FakeScryfallClient:
    def __init__(self, payloads: list[dict] | None = None) -> None:
        self.payloads = payloads or []
        self.fuzzy_calls: list[str] = []

    def fetch_card_fuzzy(self, name: str) -> dict:
        self.fuzzy_calls.append(name)
        raise RuntimeError("offline")

    def fetch_bulk_data(self) -> list[dict]:
        return [
            {
                "type": "oracle_cards",
                "jsonl_download_uri": "https://example.test/oracle.jsonl.gz",
                "download_uri": "https://example.test/oracle.json",
                "updated_at": "2026-07-20T21:03:00+00:00",
            }
        ]

    def download_bulk_file(self, download_uri: str, destination: Path) -> None:
        lines = [json.dumps(payload) for payload in self.payloads]
        with gzip.open(destination, "wt", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    def close(self) -> None:
        return None


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_normalize_card_name() -> None:
    assert normalize_card_name("Sol Ring") == normalize_card_name("sol-ring")
    assert normalize_card_name("Jace, the Mind Sculptor") == "jacethemindsculptor"


def test_lookup_local_exact_and_normalized(session: Session) -> None:
    session.add(
        Card(
            oracle_id="abc",
            name="Sol Ring",
            is_basic_land=False,
            is_token=False,
        )
    )
    session.flush()

    service = ScryfallService(session, FakeScryfallClient())
    assert service.lookup_local("sol ring") is not None
    assert service.lookup_local("Sol-Ring") is not None


def test_fetch_and_cache_uses_local_without_api(session: Session) -> None:
    session.add(
        Card(
            oracle_id="abc",
            name="Sol Ring",
            is_basic_land=False,
            is_token=False,
        )
    )
    session.flush()

    client = FakeScryfallClient()
    service = ScryfallService(session, client)
    card = service.fetch_and_cache("Sol Ring")

    assert card.name == "Sol Ring"
    assert client.fuzzy_calls == []


def test_fetch_and_cache_raises_when_offline_and_missing(session: Session) -> None:
    service = ScryfallService(session, FakeScryfallClient())

    with pytest.raises(ScryfallOfflineError):
        service.fetch_and_cache("Unknown Card")


def test_lookup_local_prefers_playable_over_art_series(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="playable",
                name="Kellan, the Kid",
                type_line="Legendary Creature — Human Faerie Rogue",
                is_basic_land=False,
                is_token=False,
            ),
            Card(
                oracle_id="art",
                name="Kellan, the Kid // Kellan, the Kid",
                type_line="Card // Card",
                is_basic_land=False,
                is_token=False,
            ),
        ]
    )
    session.flush()

    service = ScryfallService(session, FakeScryfallClient())
    card = service.lookup_local("Kellan, the Kid")

    assert card is not None
    assert card.oracle_id == "playable"


def test_lookup_local_prefers_card_over_same_named_token(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="token",
                name="Darkstar Augur",
                type_line="Token Creature — Bat Warlock",
                is_basic_land=False,
                is_token=True,
            ),
            Card(
                oracle_id="card",
                name="Darkstar Augur",
                type_line="Creature — Bat Warlock",
                is_basic_land=False,
                is_token=False,
            ),
        ]
    )
    session.flush()

    service = ScryfallService(session, FakeScryfallClient())
    card = service.lookup_local("Darkstar Augur")
    token = service.lookup_local("Darkstar Augur", prefer_token=True)

    assert card is not None
    assert card.oracle_id == "card"
    assert card.is_token is False
    assert token is not None
    assert token.oracle_id == "token"
    assert token.is_token is True


def test_bulk_sync_skips_art_series(session: Session) -> None:
    payloads = [
        {
            "oracle_id": "11111111-1111-1111-1111-111111111111",
            "name": "Arcane Signet",
            "type_line": "Artifact",
            "cmc": 2.0,
            "colors": [],
            "color_identity": [],
        },
        {
            "oracle_id": "22222222-2222-2222-2222-222222222222",
            "name": "Kellan, the Kid // Kellan, the Kid",
            "layout": "art_series",
            "type_line": "Card // Card",
            "cmc": 0.0,
            "colors": [],
            "color_identity": [],
        },
    ]
    client = FakeScryfallClient(payloads=payloads)
    service = ScryfallBulkService(session, client)

    result = service.sync_oracle_cards()

    assert result.imported_cards == 1
    assert session.get(Card, payloads[0]["oracle_id"]) is not None
    assert session.get(Card, payloads[1]["oracle_id"]) is None


def test_bulk_sync_imports_oracle_cards(session: Session) -> None:
    payload = {
        "oracle_id": "11111111-1111-1111-1111-111111111111",
        "name": "Arcane Signet",
        "type_line": "Artifact",
        "cmc": 2.0,
        "colors": [],
        "color_identity": [],
    }
    client = FakeScryfallClient(payloads=[payload])
    service = ScryfallBulkService(session, client)

    result = service.sync_oracle_cards()

    assert result.imported_cards == 1
    card = session.get(Card, payload["oracle_id"])
    assert card is not None
    assert card.name == "Arcane Signet"
    assert session.get(AppSetting, "scryfall_bulk_oracle_synced_at") is not None


def test_iter_bulk_card_payloads_reads_json_array(tmp_path: Path) -> None:
    payload = {
        "oracle_id": "22222222-2222-2222-2222-222222222222",
        "name": "Sol Ring",
        "type_line": "Artifact",
        "cmc": 1.0,
        "colors": [],
        "color_identity": [],
    }
    bulk_path = tmp_path / "oracle.json"
    bulk_path.write_text(json.dumps([payload]), encoding="utf-8")

    rows = list(_iter_bulk_card_payloads(bulk_path))

    assert rows == [payload]
