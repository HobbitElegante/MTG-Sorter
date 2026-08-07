from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_rebuilder.models.house_ban import HouseBan


class HouseBanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[HouseBan]:
        return list(
            self._session.scalars(select(HouseBan).order_by(HouseBan.name)).all()
        )

    def get(self, oracle_id: str) -> HouseBan | None:
        return self._session.get(HouseBan, oracle_id)

    def oracle_ids(self) -> set[str]:
        return set(self._session.scalars(select(HouseBan.oracle_id)).all())

    def add(self, oracle_id: str, name: str) -> HouseBan:
        existing = self.get(oracle_id)
        if existing is not None:
            existing.name = name
            return existing
        ban = HouseBan(oracle_id=oracle_id, name=name)
        self._session.add(ban)
        return ban

    def remove(self, oracle_id: str) -> bool:
        ban = self.get(oracle_id)
        if ban is None:
            return False
        self._session.delete(ban)
        return True
