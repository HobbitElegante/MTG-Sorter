from sqlalchemy import delete, select

from sqlalchemy.orm import Session

from mtg_sorter.models import CardPrint


class CardPrintRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_card(self, oracle_id: str) -> list[CardPrint]:
        return list(
            self._session.scalars(
                select(CardPrint)
                .where(CardPrint.oracle_id == oracle_id)
                .order_by(CardPrint.released_at, CardPrint.set_code)
            ).all()
        )

    def has_any(self, oracle_id: str) -> bool:
        return (
            self._session.scalar(
                select(CardPrint.id).where(CardPrint.oracle_id == oracle_id).limit(1)
            )
            is not None
        )

    def replace_for_card(
        self, oracle_id: str, prints: list[tuple[str, str | None, str | None]]
    ) -> list[CardPrint]:
        self._session.execute(
            delete(CardPrint).where(CardPrint.oracle_id == oracle_id)
        )
        rows = [
            CardPrint(
                oracle_id=oracle_id,
                set_code=set_code,
                set_name=set_name,
                released_at=released_at,
            )
            for set_code, set_name, released_at in prints
        ]
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def flush(self) -> None:
        self._session.flush()
