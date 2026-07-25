import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.models import ActivityEvent, Card
from mtg_sorter.models.enums import ActivityCategory, ActivityEventType

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
        self._session.add(event)
        self._session.flush()
        return event

    def card_name(self, oracle_id: str) -> str:
        card = self._session.get(Card, oracle_id)
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
        limit: int = 500,
    ) -> list[ActivityEventRow]:
        query = select(ActivityEvent).order_by(
            ActivityEvent.created_at.desc(),
            ActivityEvent.id.desc(),
        )
        if category == ActivityCategory.INVENTORY:
            query = query.where(
                ActivityEvent.event_type.in_(
                    [event.value for event in INVENTORY_EVENT_TYPES]
                )
            )
        elif category == ActivityCategory.DECKS:
            query = query.where(
                ActivityEvent.event_type.in_(
                    [event.value for event in DECK_EVENT_TYPES]
                )
            )
        if limit > 0:
            query = query.limit(limit)

        rows: list[ActivityEventRow] = []
        for event in self._session.scalars(query).all():
            try:
                payload = json.loads(event.payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            try:
                event_type = ActivityEventType(event.event_type)
            except ValueError:
                continue
            rows.append(
                ActivityEventRow(
                    id=event.id,
                    created_at=event.created_at,
                    event_type=event_type,
                    summary_key=event.summary,
                    payload=payload,
                )
            )
        return rows
