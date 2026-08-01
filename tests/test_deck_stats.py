from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.algorithms.deck_stats import (
    DeckStatsCard,
    compute_deck_statistics,
    count_pips,
)
from mtg_sorter.models import Base, Card, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService


def _card(
    name: str = "Test",
    quantity: int = 1,
    type_line: str | None = "Creature — Human",
    cmc: float | None = 2.0,
    mana_cost: str | None = "{1}{G}",
    is_basic_land: bool = False,
) -> DeckStatsCard:
    return DeckStatsCard(
        name=name,
        quantity=quantity,
        type_line=type_line,
        cmc=cmc,
        mana_cost=mana_cost,
        is_basic_land=is_basic_land,
    )


def test_totals_and_land_counts() -> None:
    stats = compute_deck_statistics(
        [
            _card("Forest", 10, "Basic Land — Forest", 0.0, None, True),
            _card("Command Tower", 1, "Land", 0.0, None),
            _card("Llanowar Elves", 1, "Creature — Elf Druid", 1.0, "{G}"),
        ]
    )
    assert stats.total_cards == 12
    assert stats.lands == 11
    assert stats.basic_lands == 10


def test_average_cmc_excludes_lands_and_weights_by_quantity() -> None:
    stats = compute_deck_statistics(
        [
            _card("Forest", 30, "Basic Land — Forest", 0.0, None, True),
            _card("One drop", 2, "Creature", 1.0, "{G}"),
            _card("Four drop", 1, "Sorcery", 4.0, "{3}{G}"),
        ]
    )
    assert stats.average_cmc == pytest.approx(2.0)
    assert stats.average_cmc_with_lands == pytest.approx(6 / 33)


def test_average_with_lands_treats_missing_land_cmc_as_zero() -> None:
    stats = compute_deck_statistics(
        [
            _card("Command Tower", 1, "Land", None, None),
            _card("Bear", 1, "Creature — Bear", 2.0, "{1}{G}"),
        ]
    )
    assert stats.average_cmc == pytest.approx(2.0)
    assert stats.average_cmc_with_lands == pytest.approx(1.0)


def test_average_cmc_none_without_data() -> None:
    stats = compute_deck_statistics(
        [_card("Mystery", 1, None, None, None)]
    )
    assert stats.average_cmc is None
    assert stats.average_cmc_with_lands is None
    assert stats.unknown_cards == 1


def test_multi_type_card_counts_in_each_type() -> None:
    stats = compute_deck_statistics(
        [_card("Golem", 2, "Artifact Creature — Golem", 3.0, "{3}")]
    )
    assert dict(stats.type_counts) == {"Creature": 2, "Artifact": 2}


def test_dfc_classified_by_front_face() -> None:
    stats = compute_deck_statistics(
        [
            _card(
                "Bala Ged Recovery",
                1,
                "Sorcery // Land",
                3.0,
                "{2}{G}",
            ),
            _card("Westvale Abbey", 1, "Land // Legendary Creature", 0.0, None),
        ]
    )
    assert stats.lands == 1
    assert dict(stats.type_counts) == {"Sorcery": 1}
    assert stats.curve[3].others == 1


def test_curve_splits_creatures_and_buckets_high_cmc() -> None:
    stats = compute_deck_statistics(
        [
            _card("Bear", 3, "Creature — Bear", 2.0, "{1}{G}"),
            _card("Counterspell", 2, "Instant", 2.0, "{U}{U}"),
            _card("Big spell", 1, "Sorcery", 9.0, "{7}{R}{R}"),
        ]
    )
    assert stats.curve[2].creatures == 3
    assert stats.curve[2].others == 2
    assert stats.curve[7].others == 1
    assert stats.has_curve_data


def test_lands_stay_out_of_curve_and_pips() -> None:
    stats = compute_deck_statistics(
        [_card("Forest", 35, "Basic Land — Forest", 0.0, None, True)]
    )
    assert not stats.has_curve_data
    assert stats.color_pips == ()


def test_pips_hybrid_and_phyrexian_count_each_color() -> None:
    pips = count_pips("{2}{W/U}{G/P}{C}")
    assert pips["W"] == 1
    assert pips["U"] == 1
    assert pips["G"] == 1
    assert pips["C"] == 1
    assert pips["B"] == 0


def test_pips_use_front_face_and_quantity_weighting() -> None:
    stats = compute_deck_statistics(
        [_card("DFC", 2, "Instant // Sorcery", 2.0, "{1}{U} // {3}{R}")]
    )
    assert dict(stats.color_pips) == {"U": 2}


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_deck_statistics_service(session: Session) -> None:
    commander = Card(
        oracle_id="cmd",
        name="Commander",
        type_line="Legendary Creature — Human",
        cmc=4.0,
        mana_cost="{2}{W}{W}",
        is_basic_land=False,
        is_token=False,
    )
    plains = Card(
        oracle_id="plains",
        name="Plains",
        type_line="Basic Land — Plains",
        cmc=0.0,
        is_basic_land=True,
        is_token=False,
    )
    wrath = Card(
        oracle_id="wrath",
        name="Wrath of God",
        type_line="Sorcery",
        cmc=4.0,
        mana_cost="{2}{W}{W}",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([commander, plains, wrath, deck])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="cmd",
                quantity=1,
                role=DeckCardRole.COMMANDER,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="plains",
                quantity=30,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="wrath",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()

    stats = DeckService(session).deck_statistics(deck.id)

    assert stats.total_cards == 32
    assert stats.lands == 30
    assert stats.basic_lands == 30
    assert stats.average_cmc == pytest.approx(4.0)
    assert stats.average_cmc_with_lands == pytest.approx(0.25)
    assert dict(stats.type_counts) == {"Creature": 1, "Sorcery": 1}
    assert dict(stats.color_pips) == {"W": 4}
    assert stats.curve[4].creatures == 1
    assert stats.curve[4].others == 1
