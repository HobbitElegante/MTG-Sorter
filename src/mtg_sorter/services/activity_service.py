import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from mtg_sorter.models import ActivityEvent, Deck
from mtg_sorter.models.enums import (
    ActivityCategory,
    ActivityEventType,
    DeckStatus,
)
from mtg_sorter.repositories import ActivityRepository, CardRepository, DeckRepository

INVENTORY_EVENT_TYPES = frozenset(
    {
        ActivityEventType.COPIES_ADDED,
        ActivityEventType.COPIES_REMOVED,
    }
)
DECK_EVENT_TYPES = frozenset(
    {
        ActivityEventType.DECK_ARMED,
        ActivityEventType.DECK_DISMANTLED,
        ActivityEventType.DECK_IMPORTED,
        ActivityEventType.DECK_DELETED,
        ActivityEventType.DECK_LIST_EDITED,
        ActivityEventType.PLAN_APPLIED,
    }
)
UNDOABLE_EVENT_TYPES = frozenset(
    {
        ActivityEventType.COPIES_ADDED,
        ActivityEventType.COPIES_REMOVED,
        ActivityEventType.DECK_ARMED,
        ActivityEventType.DECK_DISMANTLED,
        ActivityEventType.PLAN_APPLIED,
    }
)

HISTORY_PAGE_SIZE = 50
HISTORY_EXPORT_LIMIT = 10_000


@dataclass(frozen=True)
class ActivityEventRow:
    id: int
    created_at: datetime
    event_type: ActivityEventType
    summary_key: str
    payload: dict


class ActivityService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._events = ActivityRepository(session)
        self._cards = CardRepository(session)
        self._decks = DeckRepository(session)

    def record(
        self,
        event_type: ActivityEventType,
        summary_key: str,
        payload: dict | None = None,
    ) -> ActivityEvent:
        event = ActivityEvent(
            event_type=event_type.value,
            summary=summary_key,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
        )
        return self._events.add(event)

    def card_name(self, oracle_id: str) -> str:
        card = self._cards.get(oracle_id)
        return card.name if card is not None else oracle_id

    def record_copies_added(
        self,
        oracle_id: str,
        quantity: int,
        *,
        origin: str | None = None,
    ) -> ActivityEvent | None:
        if quantity <= 0:
            return None
        payload: dict = {
            "oracle_id": oracle_id,
            "name": self.card_name(oracle_id),
            "qty_delta": quantity,
        }
        if origin:
            payload["origin"] = origin
        return self.record(
            ActivityEventType.COPIES_ADDED,
            "history.event.copies_added",
            payload,
        )

    def record_copies_removed(
        self,
        oracle_id: str,
        quantity: int,
        *,
        origin: str | None = None,
    ) -> ActivityEvent | None:
        if quantity <= 0:
            return None
        payload: dict = {
            "oracle_id": oracle_id,
            "name": self.card_name(oracle_id),
            "qty_delta": quantity,
        }
        if origin:
            payload["origin"] = origin
        return self.record(
            ActivityEventType.COPIES_REMOVED,
            "history.event.copies_removed",
            payload,
        )

    def list_events(
        self,
        *,
        category: ActivityCategory | None = None,
        limit: int = HISTORY_PAGE_SIZE,
        before_id: int | None = None,
    ) -> list[ActivityEventRow]:
        event_types: list[str] | None = None
        if category == ActivityCategory.INVENTORY:
            event_types = [event.value for event in INVENTORY_EVENT_TYPES]
        elif category == ActivityCategory.DECKS:
            event_types = [event.value for event in DECK_EVENT_TYPES]

        rows: list[ActivityEventRow] = []
        for event in self._events.list_events(
            event_types=event_types,
            before_id=before_id,
            limit=limit,
        ):
            row = self._to_row(event)
            if row is not None:
                rows.append(row)
        return rows

    def events_csv(
        self,
        *,
        category: ActivityCategory | None = None,
        limit: int = HISTORY_EXPORT_LIMIT,
    ) -> str:
        rows = self.list_events(category=category, limit=limit)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["id", "created_at", "event_type", "summary", "payload_json"]
        )
        for row in rows:
            writer.writerow(
                [
                    row.id,
                    row.created_at.isoformat(),
                    row.event_type.value,
                    row.summary_key,
                    json.dumps(row.payload, ensure_ascii=False),
                ]
            )
        return buffer.getvalue()

    def latest_event(self) -> ActivityEventRow | None:
        rows = self.list_events(limit=1)
        return rows[0] if rows else None

    def can_undo_last(self) -> bool:
        latest = self.latest_event()
        return latest is not None and latest.event_type in UNDOABLE_EVENT_TYPES

    def undo_last(self) -> ActivityEventRow:
        latest = self.latest_event()
        if latest is None or latest.event_type not in UNDOABLE_EVENT_TYPES:
            raise ValueError("Nothing to undo")

        if latest.event_type == ActivityEventType.COPIES_ADDED:
            self._undo_copies_added(latest)
        elif latest.event_type == ActivityEventType.COPIES_REMOVED:
            self._undo_copies_removed(latest)
        elif latest.event_type == ActivityEventType.DECK_ARMED:
            self._undo_deck_armed(latest)
        elif latest.event_type == ActivityEventType.DECK_DISMANTLED:
            self._undo_deck_dismantled(latest)
        elif latest.event_type == ActivityEventType.PLAN_APPLIED:
            self._undo_plan_applied(latest)
        else:
            raise ValueError(f"Cannot undo event type {latest.event_type}")

        undone = self.record(
            ActivityEventType.ACTIVITY_UNDONE,
            "history.event.undone",
            {
                "undone_event_id": latest.id,
                "undone_event_type": latest.event_type.value,
                "summary_key": latest.summary_key,
                **{
                    key: value
                    for key, value in latest.payload.items()
                    if key in {"name", "deck_name", "qty_delta"}
                },
            },
        )
        row = self._to_row(undone)
        assert row is not None
        return row

    def _undo_copies_added(self, event: ActivityEventRow) -> None:
        from mtg_sorter.services.deck_service import InventoryService

        oracle_id = event.payload.get("oracle_id")
        qty = int(event.payload.get("qty_delta") or 0)
        if not isinstance(oracle_id, str) or qty <= 0:
            raise ValueError("Invalid copies-added event payload")
        removed = InventoryService(self._session).remove_free_copies(
            oracle_id, qty, record_activity=False
        )
        if removed != qty:
            raise ValueError(
                f"Not enough free copies to undo (need {qty}, free {removed})"
            )

    def _undo_copies_removed(self, event: ActivityEventRow) -> None:
        from mtg_sorter.services.deck_service import InventoryService

        oracle_id = event.payload.get("oracle_id")
        qty = int(event.payload.get("qty_delta") or 0)
        if not isinstance(oracle_id, str) or qty <= 0:
            raise ValueError("Invalid copies-removed event payload")
        InventoryService(self._session).add_copy(
            oracle_id, qty, record_activity=False
        )

    def _undo_deck_armed(self, event: ActivityEventRow) -> None:
        from mtg_sorter.services.deck_service import DeckService

        deck = self._require_deck(event.payload.get("deck_id"))
        if deck.status != DeckStatus.ARMED:
            raise ValueError(f"Deck {deck.name} is not armed")
        DeckService(self._session).set_status(
            deck, DeckStatus.DISMANTLED, record_activity=False
        )

    def _undo_deck_dismantled(self, event: ActivityEventRow) -> None:
        from mtg_sorter.services.deck_service import DeckService

        deck = self._require_deck(event.payload.get("deck_id"))
        if deck.status != DeckStatus.DISMANTLED:
            raise ValueError(f"Deck {deck.name} is not dismantled")
        DeckService(self._session).set_status(
            deck, DeckStatus.ARMED, record_activity=False
        )

    def _undo_plan_applied(self, event: ActivityEventRow) -> None:
        from mtg_sorter.services.deck_service import DeckService

        decks = DeckService(self._session)
        target = self._require_deck(event.payload.get("deck_id"))
        donor_ids = event.payload.get("donor_deck_ids") or []
        if not isinstance(donor_ids, list):
            raise ValueError("Invalid plan-applied event payload")
        donors: list[Deck] = []
        for raw_id in donor_ids:
            donors.append(self._require_deck(raw_id))

        if target.status != DeckStatus.ARMED:
            raise ValueError(f"Target deck {target.name} is not armed")
        decks.set_status(target, DeckStatus.DISMANTLED, record_activity=False)
        for donor in donors:
            self._session.refresh(donor)
            if donor.status != DeckStatus.DISMANTLED:
                raise ValueError(f"Donor deck {donor.name} is not dismantled")
            decks.set_status(donor, DeckStatus.ARMED, record_activity=False)

    def _require_deck(self, deck_id: object) -> Deck:
        try:
            resolved_id = int(deck_id)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("Missing or invalid deck_id in event payload") from exc
        deck = self._decks.get(resolved_id)
        if deck is None:
            raise ValueError(f"Deck {resolved_id} not found")
        return deck

    @staticmethod
    def _to_row(event: ActivityEvent) -> ActivityEventRow | None:
        try:
            payload = json.loads(event.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        try:
            event_type = ActivityEventType(event.event_type)
        except ValueError:
            return None
        return ActivityEventRow(
            id=event.id,
            created_at=event.created_at,
            event_type=event_type,
            summary_key=event.summary,
            payload=payload,
        )
