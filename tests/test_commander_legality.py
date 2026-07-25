from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.algorithms.card_utils import (
    commander_legality_from_payload,
    is_commander_legality_issue,
)
from mtg_sorter.models import Base, Card, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService
from mtg_sorter.services.scryfall_service import ScryfallService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db_session:
        yield db_session


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("banned", True),
        ("not_legal", True),
        ("restricted", True),
        ("legal", False),
        (None, False),
        ("", False),
    ],
)
def test_is_commander_legality_issue(value: str | None, expected: bool) -> None:
    assert is_commander_legality_issue(value) is expected


def test_commander_legality_from_payload() -> None:
    assert (
        commander_legality_from_payload(
            {"legalities": {"commander": "Banned"}}
        )
        == "banned"
    )
    assert commander_legality_from_payload({}) is None


def test_deck_commander_legality_issues_are_advisory(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="legal",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
                commander_legality="legal",
            ),
            Card(
                oracle_id="banned",
                name="Coalition Victory",
                is_basic_land=False,
                is_token=False,
                commander_legality="banned",
            ),
            Card(
                oracle_id="unknown",
                name="Mystery Card",
                is_basic_land=False,
                is_token=False,
                commander_legality=None,
            ),
        ]
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="legal",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="banned",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="unknown",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()

    issues = DeckService(session).commander_legality_issues(deck.id)
    assert len(issues) == 1
    assert issues[0].name == "Coalition Victory"
    assert issues[0].legality == "banned"


def test_deck_commander_rule_issues_from_cached_card_data(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="ghen",
                name="Ghen, Arcanum Weaver",
                is_basic_land=False,
                is_token=False,
                color_identity="WBR",
                type_line="Legendary Creature — Human Shaman",
            ),
            Card(
                oracle_id="in_identity",
                name="Anguished Unmaking",
                is_basic_land=False,
                is_token=False,
                color_identity="WB",
            ),
            Card(
                oracle_id="off_identity",
                name="Cultivate",
                is_basic_land=False,
                is_token=False,
                color_identity="G",
            ),
            Card(
                oracle_id="forest",
                name="Forest",
                is_basic_land=True,
                is_token=False,
                color_identity="G",
            ),
        ]
    )
    deck = Deck(name="Ghen", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="ghen",
                quantity=1,
                role=DeckCardRole.COMMANDER,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="in_identity",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="off_identity",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="forest",
                quantity=10,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()

    issues = DeckService(session).commander_rule_issues(deck.id)
    color_issues = [
        issue
        for issue in issues
        if issue.kind.value == "color_identity"
    ]

    # Basics are an unlimited shared pool, so the Forest is not flagged.
    assert [issue.name for issue in color_issues] == ["Cultivate"]
    assert color_issues[0].colors == "G"
    assert color_issues[0].allowed == "WBR"


def test_deck_commander_rule_issues_flag_illegal_partner(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="thrasios",
                name="Thrasios, Triton Hero",
                is_basic_land=False,
                is_token=False,
                color_identity="GU",
                oracle_text="Partner (You can have two commanders if both have partner.)",
                type_line="Legendary Creature — Merfolk Wizard",
            ),
            Card(
                oracle_id="plain",
                name="Plain Legend",
                is_basic_land=False,
                is_token=False,
                color_identity="R",
                oracle_text="Haste",
                type_line="Legendary Creature — Goblin",
            ),
        ]
    )
    deck = Deck(name="Partners", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="thrasios",
                quantity=1,
                role=DeckCardRole.COMMANDER,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="plain",
                quantity=1,
                role=DeckCardRole.PARTNER,
            ),
        ]
    )
    session.flush()

    issues = [
        issue
        for issue in DeckService(session).commander_rule_issues(deck.id)
        if issue.kind.value == "pairing"
    ]

    assert len(issues) == 1
    assert issues[0].name == "Plain Legend"
    assert issues[0].commander == "Thrasios, Triton Hero"


class _FakeCollectionClient:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []
        self._by_id = {
            "sol": {
                "oracle_id": "sol",
                "name": "Sol Ring",
                "type_line": "Artifact",
                "legalities": {"commander": "legal"},
                "image_uris": {"normal": "https://example.test/sol.jpg"},
            },
            "dfc": {
                "oracle_id": "dfc",
                "name": "Delver of Secrets // Insectile Aberration",
                "type_line": "Creature — Human Wizard",
                "legalities": {"commander": "legal"},
                "card_faces": [
                    {"image_uris": {"normal": "https://example.test/front.jpg"}},
                    {"image_uris": {"normal": "https://example.test/back.jpg"}},
                ],
            },
            "banned": {
                "oracle_id": "banned",
                "name": "Coalition Victory",
                "type_line": "Sorcery",
                "legalities": {"commander": "banned"},
            },
        }

    def fetch_cards_collection(self, identifiers: list[dict[str, str]]) -> dict:
        self.calls.append(identifiers)
        data = []
        for ident in identifiers:
            oracle_id = ident.get("oracle_id")
            if oracle_id in self._by_id:
                data.append(self._by_id[oracle_id])
        return {"data": data, "not_found": []}

    def close(self) -> None:
        return None


def test_refresh_collection_card_data(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="sol",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
                commander_legality=None,
            ),
            Card(
                oracle_id="banned",
                name="Coalition Victory",
                is_basic_land=False,
                is_token=False,
                commander_legality=None,
            ),
        ]
    )
    session.flush()
    session.add(CardCopy(card_id="sol"))
    session.flush()

    client = _FakeCollectionClient()
    service = ScryfallService(session, client=client)
    count = service.refresh_collection_card_data()

    assert count == 1  # only inventory copy (sol); banned not in collection
    assert session.get(Card, "sol").commander_legality == "legal"
    assert session.get(Card, "banned").commander_legality is None
    assert len(client.calls) == 1
    assert client.calls[0] == [{"oracle_id": "sol"}]


def test_refresh_includes_deck_list_cards(session: Session) -> None:
    session.add(
        Card(
            oracle_id="banned",
            name="Coalition Victory",
            is_basic_land=False,
            is_token=False,
            commander_legality=None,
        )
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="banned",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    client = _FakeCollectionClient()
    count = ScryfallService(session, client=client).refresh_collection_card_data()
    assert count == 1
    assert session.get(Card, "banned").commander_legality == "banned"


def test_refresh_backfills_image_uris_including_back_face(session: Session) -> None:
    session.add_all(
        [
            Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False),
            Card(
                oracle_id="dfc",
                name="Delver of Secrets // Insectile Aberration",
                is_basic_land=False,
                is_token=False,
            ),
        ]
    )
    session.flush()
    session.add_all([CardCopy(card_id="sol"), CardCopy(card_id="dfc")])
    session.flush()

    ScryfallService(session, client=_FakeCollectionClient()).refresh_collection_card_data()

    assert session.get(Card, "sol").image_uri == "https://example.test/sol.jpg"
    assert session.get(Card, "sol").image_uri_back is None
    dfc = session.get(Card, "dfc")
    assert dfc.image_uri == "https://example.test/front.jpg"
    assert dfc.image_uri_back == "https://example.test/back.jpg"
