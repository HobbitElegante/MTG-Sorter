from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_rebuilder.models import ActivityEvent


class ActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: ActivityEvent) -> ActivityEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def get(self, event_id: int) -> ActivityEvent | None:
        return self._session.get(ActivityEvent, event_id)

    def list_events(
        self,
        *,
        event_types: Sequence[str] | None = None,
        before_id: int | None = None,
        limit: int = 0,
    ) -> list[ActivityEvent]:
        query = select(ActivityEvent).order_by(ActivityEvent.id.desc())
        if event_types is not None:
            query = query.where(ActivityEvent.event_type.in_(list(event_types)))
        if before_id is not None:
            query = query.where(ActivityEvent.id < before_id)
        if limit > 0:
            query = query.limit(limit)
        return list(self._session.scalars(query).all())
