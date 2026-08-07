import gzip
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mtg_rebuilder.models import AppSetting, Base, Card
from mtg_rebuilder.services.scryfall_bulk_service import (
    ScryfallBulkService,
    _iter_bulk_card_payloads,
)
from mtg_rebuilder.services.scryfall_service import (
    ScryfallOfflineError,
    ScryfallService,
    card_from_scryfall,
    normalize_card_name,
)


class FakeScryfallClient:
    def __init__(
        self,
        payloads: list[dict] | None = None,
        *,
        bulk_entries: list[dict] | None = None,
        payloads_by_type: dict[str, list[dict]] | None = None,
    ) -> None:
        self.payloads = payloads or []
        self.payloads_by_type = payloads_by_type or {}
        self.fuzzy_calls: list[str] = []
        self.downloaded_urls: list[str] = []
        self.bulk_entries = bulk_entries or [
            {
                "type": "oracle_cards",
                "jsonl_download_uri": "https://example.test/oracle.jsonl.gz",
                "download_uri": "https://example.test/oracle.json",
                "updated_at": "2026-07-20T21:03:00+00:00",
            },
            {
                "type": "unique_artwork",
                "jsonl_download_uri": "https://example.test/unique.jsonl.gz",
                "download_uri": "https://example.test/unique.json",
                "updated_at": "2026-07-20T21:04:00+00:00",
            },
        ]

    def fetch_card_fuzzy(self, name: str) -> dict:
        self.fuzzy_calls.append(name)
        raise RuntimeError("offline")

    def fetch_bulk_data(self) -> list[dict]:
        return self.bulk_entries

    def download_file(self, url: str, destination: Path) -> None:
        self.downloaded_urls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith(".jpg") or "card_images" in url:
            destination.write_bytes(b"fake-jpeg")
            return
        pack_type = "oracle_cards"
        if "unique" in url:
            pack_type = "unique_artwork"
        payloads = self.payloads_by_type.get(pack_type, self.payloads)
        lines = [json.dumps(payload) for payload in payloads]
        with gzip.open(destination, "wt", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    def download_bulk_file(self, download_uri: str, destination: Path) -> None:
        self.download_file(download_uri, destination)

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
    assert session.get(AppSetting, "scryfall_bulk_pack_type").value == "oracle_cards"


def test_card_from_scryfall_reads_both_faces_of_a_dfc() -> None:
    card = card_from_scryfall(
        {
            "oracle_id": "dfc-1",
            "name": "Delver of Secrets // Insectile Aberration",
            "type_line": "Creature — Human Wizard",
            "cmc": 1.0,
            "rarity": "Rare",
            "card_faces": [
                {
                    "name": "Delver of Secrets",
                    "image_uris": {"normal": "https://example.test/front.jpg"},
                },
                {
                    "name": "Insectile Aberration",
                    "image_uris": {"normal": "https://example.test/back.jpg"},
                },
            ],
        }
    )

    assert card.image_uri == "https://example.test/front.jpg"
    assert card.image_uri_back == "https://example.test/back.jpg"
    assert card.rarity == "rare"


def test_card_from_scryfall_leaves_back_empty_for_split_cards() -> None:
    card = card_from_scryfall(
        {
            "oracle_id": "split-1",
            "name": "Fire // Ice",
            "type_line": "Instant // Instant",
            "cmc": 2.0,
            "image_uris": {"normal": "https://example.test/fire-ice.jpg"},
            "card_faces": [{"name": "Fire"}, {"name": "Ice"}],
        }
    )

    assert card.image_uri == "https://example.test/fire-ice.jpg"
    assert card.image_uri_back is None


def test_card_from_scryfall_reversible_uses_face_oracle_id() -> None:
    card = card_from_scryfall(
        {
            "layout": "reversible_card",
            "name": "Ghalta, Primal Hunger // Ghalta, Primal Hunger",
            "color_identity": ["G"],
            "card_faces": [
                {
                    "oracle_id": "ghalta-oracle",
                    "name": "Ghalta, Primal Hunger",
                    "type_line": "Legendary Creature — Elder Dinosaur",
                    "mana_cost": "{10}{G}{G}",
                    "cmc": 12.0,
                    "colors": ["G"],
                    "image_uris": {"normal": "https://example.test/ghalta-front.jpg"},
                },
                {
                    "oracle_id": "ghalta-oracle",
                    "name": "Ghalta, Primal Hunger",
                    "image_uris": {"normal": "https://example.test/ghalta-back.jpg"},
                },
            ],
        }
    )

    assert card.oracle_id == "ghalta-oracle"
    assert card.name == "Ghalta, Primal Hunger"
    assert card.type_line == "Legendary Creature — Elder Dinosaur"
    assert card.cmc == 12.0
    assert card.colors == "G"
    assert card.image_uri == "https://example.test/ghalta-front.jpg"
    assert card.image_uri_back is None


def test_bulk_sync_unique_artwork_skips_payloads_without_oracle_id(
    session: Session,
) -> None:
    oracle_id = "11111111-1111-1111-1111-111111111111"
    payloads = [
        {
            "layout": "reversible_card",
            "name": "No Face Id // No Face Id",
            "card_faces": [{"name": "No Face Id"}, {"name": "No Face Id"}],
        },
        {
            "oracle_id": oracle_id,
            "name": "Sol Ring",
            "type_line": "Artifact",
            "cmc": 1.0,
            "colors": [],
            "color_identity": [],
            "image_uris": {"normal": "https://example.test/sol.jpg"},
        },
    ]
    client = FakeScryfallClient(
        payloads_by_type={"unique_artwork": payloads, "oracle_cards": []}
    )
    service = ScryfallBulkService(session, client)

    result = service.sync_bulk("unique_artwork")

    assert result.imported_cards == 1
    assert session.get(Card, oracle_id) is not None


def test_bulk_sync_unique_artwork_collapses_oracle_id(session: Session) -> None:
    oracle_id = "11111111-1111-1111-1111-111111111111"
    payloads = [
        {
            "oracle_id": oracle_id,
            "name": "Sol Ring",
            "type_line": "Artifact",
            "cmc": 1.0,
            "colors": [],
            "color_identity": [],
            "image_uris": {"normal": "https://example.test/art-a.jpg"},
        },
        {
            "oracle_id": oracle_id,
            "name": "Sol Ring",
            "type_line": "Artifact",
            "cmc": 1.0,
            "colors": [],
            "color_identity": [],
            "image_uris": {"normal": "https://example.test/art-b.jpg"},
        },
    ]
    client = FakeScryfallClient(
        payloads_by_type={"unique_artwork": payloads, "oracle_cards": []}
    )
    service = ScryfallBulkService(session, client)

    result = service.sync_bulk("unique_artwork")

    assert result.imported_cards == 2
    assert result.pack_type == "unique_artwork"
    card = session.get(Card, oracle_id)
    assert card is not None
    assert card.image_uri == "https://example.test/art-b.jpg"
    assert session.get(AppSetting, "scryfall_bulk_pack_type").value == "unique_artwork"


def test_bulk_update_available_when_remote_newer(session: Session) -> None:
    client = FakeScryfallClient(
        payloads=[
            {
                "oracle_id": "11111111-1111-1111-1111-111111111111",
                "name": "Sol Ring",
                "type_line": "Artifact",
                "cmc": 1.0,
                "colors": [],
                "color_identity": [],
            }
        ]
    )
    service = ScryfallBulkService(session, client)
    service.sync_oracle_cards()

    client.bulk_entries = [
        {
            "type": "oracle_cards",
            "jsonl_download_uri": "https://example.test/oracle.jsonl.gz",
            "updated_at": "2026-07-24T12:00:00+00:00",
        },
        {
            "type": "unique_artwork",
            "jsonl_download_uri": "https://example.test/unique.jsonl.gz",
            "updated_at": "2026-07-24T12:00:00+00:00",
        },
    ]
    status = service.check_remote_status()

    assert status.update_available is True
    assert status.remote_updated_at == "2026-07-24T12:00:00+00:00"
    assert status.pack_type == "oracle_cards"


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
