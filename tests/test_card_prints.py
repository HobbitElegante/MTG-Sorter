import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mtg_sorter.models import Base, Card, CardPrint
from mtg_sorter.services.scryfall_service import ScryfallService, prints_from_scryfall


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db_session:
        db_session.add(
            Card(
                oracle_id="sol",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
            )
        )
        db_session.flush()
        yield db_session


class _FakePrintsClient:
    def __init__(self, payloads: list[dict] | None = None, fail: bool = False) -> None:
        self.payloads = payloads or []
        self.fail = fail
        self.calls = 0

    def fetch_card_prints(self, oracle_id: str) -> list[dict]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("offline")
        return self.payloads

    def close(self) -> None:
        return None


def test_prints_from_scryfall_dedupes_by_set_and_sorts_by_release() -> None:
    rows = prints_from_scryfall(
        [
            {"set": "c21", "set_name": "Commander 2021", "released_at": "2021-04-23"},
            {"set": "c21", "set_name": "Commander 2021", "released_at": "2021-04-23"},
            {"set": "ltr", "set_name": "The Lord of the Rings", "released_at": "2023-06-23"},
            {"set_name": "No code"},
        ]
    )

    assert rows == [
        ("C21", "Commander 2021", "2021-04-23"),
        ("LTR", "The Lord of the Rings", "2023-06-23"),
    ]


def test_list_prints_caches_after_first_lookup(session: Session) -> None:
    client = _FakePrintsClient(
        [
            {"set": "c21", "set_name": "Commander 2021", "released_at": "2021-04-23"},
            {"set": "ltr", "set_name": "The Lord of the Rings", "released_at": "2023-06-23"},
        ]
    )
    service = ScryfallService(session, client=client)

    first = service.list_prints("sol")
    second = service.list_prints("sol")

    assert first == [("C21", "Commander 2021"), ("LTR", "The Lord of the Rings")]
    assert second == first
    assert client.calls == 1
    assert session.query(CardPrint).count() == 2


def test_list_prints_falls_back_to_cache_when_offline(session: Session) -> None:
    session.add(CardPrint(oracle_id="sol", set_code="C21", set_name="Commander 2021"))
    session.flush()
    client = _FakePrintsClient(fail=True)

    prints = ScryfallService(session, client=client).list_prints("sol", refresh=True)

    assert prints == [("C21", "Commander 2021")]


def test_list_prints_offline_without_cache_returns_empty(session: Session) -> None:
    prints = ScryfallService(session, client=_FakePrintsClient(fail=True)).list_prints("sol")

    assert prints == []
