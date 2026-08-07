from dataclasses import dataclass

from sqlalchemy.orm import Session

from mtg_rebuilder.config import HOUSE_BANNED_LEGALITY
from mtg_rebuilder.repositories import DeckRepository, HouseBanRepository
from mtg_rebuilder.services.deck_service import CommanderLegalityIssue


@dataclass(frozen=True)
class HouseBanRow:
    oracle_id: str
    name: str


class HouseBanService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._bans = HouseBanRepository(session)
        self._decks = DeckRepository(session)

    def list_bans(self) -> list[HouseBanRow]:
        return [
            HouseBanRow(oracle_id=ban.oracle_id, name=ban.name)
            for ban in self._bans.list_all()
        ]

    def oracle_ids(self) -> set[str]:
        return self._bans.oracle_ids()

    def add(self, oracle_id: str, name: str) -> None:
        self._bans.add(oracle_id, name)
        self._session.flush()

    def remove(self, oracle_id: str) -> bool:
        removed = self._bans.remove(oracle_id)
        if removed:
            self._session.flush()
        return removed

    def house_ban_issues(
        self, deck_id: int, *, banned: set[str] | None = None
    ) -> list[CommanderLegalityIssue]:
        banned_ids = self._bans.oracle_ids() if banned is None else banned
        if not banned_ids:
            return []
        issues: list[CommanderLegalityIssue] = []
        for oracle_id, name, _legality in self._decks.commander_legality_rows(deck_id):
            if oracle_id not in banned_ids:
                continue
            issues.append(
                CommanderLegalityIssue(
                    oracle_id=oracle_id,
                    name=name,
                    legality=HOUSE_BANNED_LEGALITY,
                )
            )
        return sorted(issues, key=lambda item: item.name.casefold())
