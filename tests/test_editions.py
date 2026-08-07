import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mtg_rebuilder.i18n import Translator
from mtg_rebuilder.models import Base, Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_rebuilder.models.enums import DeckCardRole, DeckStatus
from mtg_rebuilder.services.browse_service import BrowseService, InventorySummaryRow
from mtg_rebuilder.services.deck_service import InventoryService
from mtg_rebuilder.services.decklist_parser import parse_decklist
from mtg_rebuilder.services.optimization_service import OptimizationService
from mtg_rebuilder.services.settings_service import SettingsService
from mtg_rebuilder.ui.inventory_display import format_edition_summary


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db_session:
        yield db_session


def _row(editions: tuple[tuple[str | None, int], ...]) -> InventorySummaryRow:
    return InventorySummaryRow(
        oracle_id="sol",
        card_name="Sol Ring",
        total_copies=sum(count for _, count in editions),
        free_copies=0,
        assigned_decks=(),
        editions=editions,
    )


def test_track_editions_setting_defaults_to_off(session: Session) -> None:
    settings = SettingsService(session)

    assert settings.get_track_editions() is False

    settings.set_track_editions(True)
    assert settings.get_track_editions() is True

    settings.set_track_editions(False)
    assert settings.get_track_editions() is False


def test_edition_summary_formats() -> None:
    assert format_edition_summary(_row(())) == "-"
    assert format_edition_summary(_row((("C21", 3),))) == "C21"
    assert format_edition_summary(_row(((None, 2),))) == "-"
    assert format_edition_summary(_row((("C21", 2), (None, 1)))) == "C21 x2, - x1"


def test_inventory_groups_copies_by_edition(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    session.flush()
    session.add_all(
        [
            CardCopy(card_id="sol", edition="C21"),
            CardCopy(card_id="sol", edition="C21"),
            CardCopy(card_id="sol", edition=None),
            CardCopy(card_id="sol", edition="LTR"),
        ]
    )
    session.flush()

    rows = BrowseService(session).list_inventory(include_editions=True)

    assert len(rows) == 1
    assert rows[0].total_copies == 4
    # Most copies first, unspecified last.
    assert rows[0].editions == (("C21", 2), ("LTR", 1), (None, 1))
    assert format_edition_summary(rows[0]) == "C21 x2, LTR x1, - x1"


def test_inventory_skips_edition_lookup_when_disabled(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    session.flush()
    session.add(CardCopy(card_id="sol", edition="C21"))
    session.flush()

    rows = BrowseService(session).list_inventory()

    assert rows[0].editions == ()
    assert format_edition_summary(rows[0]) == "-"


def test_set_copy_editions_normalizes_and_clears(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    session.flush()
    inventory = InventoryService(session)
    copies = inventory.add_copy("sol", 2, record_activity=False)

    changed = inventory.set_copy_editions(
        {copies[0].id: " c21 ", copies[1].id: "   "}
    )

    assert changed == 1
    assert copies[0].edition == "C21"
    assert copies[1].edition is None


def test_list_copies_with_deck_reports_where_each_copy_lives(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    deck = Deck(name="Ghen", status=DeckStatus.ARMED)
    session.add(deck)
    session.flush()
    inventory = InventoryService(session)
    copies = inventory.add_copy("sol", 2, record_activity=False)
    session.add(CardAssignment(card_copy_id=copies[0].id, deck_id=deck.id))
    session.flush()

    details = inventory.list_copies_with_deck("sol")

    assert [detail.deck_name for detail in details] == ["Ghen", None]


def test_add_copy_records_edition(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    session.flush()

    copies = InventoryService(session).add_copy(
        "sol", 2, edition="c21", record_activity=False
    )

    assert [copy.edition for copy in copies] == ["c21", "c21"]


def test_parser_captures_set_code_when_present() -> None:
    lines = parse_decklist("1 Sol Ring (C21) 263\n1 Cultivate\n1 Catalog (PLST) SOI-51")

    by_name = {line.name: line.set_code for line in lines}
    assert by_name == {"Sol Ring": "C21", "Cultivate": None, "Catalog": "PLST"}


def test_apply_plan_reports_copies_without_edition(session: Session) -> None:
    session.add_all(
        [
            Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False),
            Card(
                oracle_id="forest",
                name="Forest",
                is_basic_land=True,
                is_token=False,
            ),
        ]
    )
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor = Deck(name="Donor", status=DeckStatus.ARMED)
    session.add_all([target, donor])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=target.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN
            ),
            DeckCard(
                deck_id=target.id, card_id="forest", quantity=5, role=DeckCardRole.MAIN
            ),
            DeckCard(
                deck_id=donor.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN
            ),
        ]
    )
    session.flush()
    copy = CardCopy(card_id="sol")
    session.add(copy)
    session.flush()
    session.add(CardAssignment(card_copy_id=copy.id, deck_id=donor.id))
    session.flush()

    service = OptimizationService(session)
    plan = service.plan_assembly(target.id)
    moved = service.apply_assembly_plan(target.id, plan.result.solutions[0])

    # Basics never become copies, so only Sol Ring needs an edition.
    assert [item.card_name for item in moved] == ["Sol Ring"]
    assert moved[0].copy_id == copy.id


def test_apply_plan_skips_copies_that_already_have_an_edition(session: Session) -> None:
    session.add(
        Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    )
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor = Deck(name="Donor", status=DeckStatus.ARMED)
    session.add_all([target, donor])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=target.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN
            ),
            DeckCard(
                deck_id=donor.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN
            ),
        ]
    )
    session.flush()
    copy = CardCopy(card_id="sol", edition="C21")
    session.add(copy)
    session.flush()
    session.add(CardAssignment(card_copy_id=copy.id, deck_id=donor.id))
    session.flush()

    service = OptimizationService(session)
    plan = service.plan_assembly(target.id)

    assert service.apply_assembly_plan(target.id, plan.result.solutions[0]) == []


def test_edition_summary_translations_exist() -> None:
    for locale in ("en", "es"):
        translator = Translator(locale)
        for key in (
            "inventory.table.edition",
            "inventory.editions.title",
            "inventory.editions.copy_label",
            "inventory.editions.skip",
            "browse.overview.track_editions",
            "optimize.solution.suggested",
            "decks.rules.color_identity",
        ):
            assert translator.t(key) != key
