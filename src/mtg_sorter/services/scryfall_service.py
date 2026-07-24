import re
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import (
    commander_legality_from_payload,
    is_art_series_type_line,
    is_basic_land_type_line,
    is_token_type_line,
)
from mtg_sorter.api.scryfall_client import ScryfallClient
from mtg_sorter.config import SCRYFALL_COLLECTION_BATCH_SIZE
from mtg_sorter.models import Card, CardCopy
from mtg_sorter.models.deck import DeckCard


def normalize_card_name(name: str) -> str:
    lowered = name.casefold().strip()
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _is_lookup_candidate(card: Card) -> bool:
    return not is_art_series_type_line(card.type_line)


def _pick_preferred_card(candidates: list[Card], *, prefer_token: bool) -> Card | None:
    """Prefer the playable card over a same-named token (or the reverse)."""
    usable = [card for card in candidates if _is_lookup_candidate(card)]
    if not usable:
        return None
    if prefer_token:
        tokens = [card for card in usable if card.is_token]
        if tokens:
            return tokens[0]
        return usable[0]
    playable = [card for card in usable if not card.is_token]
    if playable:
        return playable[0]
    return usable[0]


def card_from_scryfall(payload: dict) -> Card:
    image_uri = None
    image_uris = payload.get("image_uris")
    if isinstance(image_uris, dict):
        image_uri = image_uris.get("normal")
    elif isinstance(payload.get("card_faces"), list) and payload["card_faces"]:
        face = payload["card_faces"][0]
        if isinstance(face, dict):
            face_images = face.get("image_uris")
            if isinstance(face_images, dict):
                image_uri = face_images.get("normal")

    type_line = payload.get("type_line")
    return Card(
        oracle_id=payload["oracle_id"],
        name=payload["name"],
        mana_cost=payload.get("mana_cost"),
        type_line=type_line,
        oracle_text=payload.get("oracle_text"),
        colors="".join(payload.get("colors") or []),
        color_identity="".join(payload.get("color_identity") or []),
        cmc=float(payload.get("cmc") or 0),
        image_uri=image_uri,
        commander_legality=commander_legality_from_payload(payload),
        is_basic_land=is_basic_land_type_line(type_line),
        is_token=is_token_type_line(type_line),
    )


class ScryfallOfflineError(RuntimeError):
    pass


class ScryfallService:
    def __init__(self, session: Session, client: ScryfallClient | None = None) -> None:
        self._session = session
        self._client = client or ScryfallClient()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def lookup_local(self, name: str, *, prefer_token: bool = False) -> Card | None:
        trimmed = name.strip()
        if not trimmed:
            return None

        exact_matches = list(
            self._session.scalars(
                select(Card).where(func.lower(Card.name) == trimmed.casefold())
            ).all()
        )
        exact = _pick_preferred_card(exact_matches, prefer_token=prefer_token)
        if exact is not None:
            return exact

        normalized_query = normalize_card_name(trimmed)
        if normalized_query:
            normalized_matches = [
                card
                for card in self._session.scalars(select(Card)).all()
                if normalize_card_name(card.name) == normalized_query
            ]
            normalized = _pick_preferred_card(
                normalized_matches, prefer_token=prefer_token
            )
            if normalized is not None:
                return normalized

        fuzzy_matches = list(
            self._session.scalars(
                select(Card).where(Card.name.ilike(f"%{trimmed}%")).limit(20)
            ).all()
        )
        preferred_fuzzy = [
            card
            for card in fuzzy_matches
            if _is_lookup_candidate(card)
            and (card.is_token if prefer_token else not card.is_token)
        ]
        if len(preferred_fuzzy) == 1:
            return preferred_fuzzy[0]
        if len(preferred_fuzzy) == 0:
            fallback = _pick_preferred_card(fuzzy_matches, prefer_token=prefer_token)
            # Only accept a sole fuzzy fallback to avoid ambiguous names.
            usable = [card for card in fuzzy_matches if _is_lookup_candidate(card)]
            if len(usable) == 1:
                return fallback
        return None

    def upsert_from_payload(self, payload: dict) -> Card:
        card = self._session.get(Card, payload["oracle_id"])
        if card is None:
            card = card_from_scryfall(payload)
            self._session.add(card)
        else:
            refreshed = card_from_scryfall(payload)
            card.name = refreshed.name
            card.mana_cost = refreshed.mana_cost
            card.type_line = refreshed.type_line
            card.oracle_text = refreshed.oracle_text
            card.colors = refreshed.colors
            card.color_identity = refreshed.color_identity
            card.cmc = refreshed.cmc
            card.image_uri = refreshed.image_uri
            card.commander_legality = refreshed.commander_legality
            card.is_basic_land = refreshed.is_basic_land
            card.is_token = refreshed.is_token
        self._session.flush()
        return card

    def fetch_and_cache(self, name: str, *, prefer_token: bool = False) -> Card:
        cached = self.lookup_local(name, prefer_token=prefer_token)
        if cached is not None:
            return cached

        try:
            payload = self._client.fetch_card_fuzzy(name)
        except Exception as exc:
            raise ScryfallOfflineError(
                f"Card '{name}' is not cached locally and Scryfall is unavailable."
            ) from exc

        card = self.upsert_from_payload(payload)
        if prefer_token == card.is_token:
            return card

        # Named API usually returns the playable card; if we wanted the other
        # side of a shared name, try the local cache again after upserting.
        preferred = self.lookup_local(name, prefer_token=prefer_token)
        return preferred if preferred is not None else card

    def cached_card_count(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(Card)) or 0)

    def collection_oracle_ids(self) -> list[str]:
        """Oracle ids for physical inventory copies and cards on deck lists."""
        copy_ids = set(self._session.scalars(select(CardCopy.card_id).distinct()).all())
        deck_ids = set(self._session.scalars(select(DeckCard.card_id).distinct()).all())
        return sorted(copy_ids | deck_ids)

    def refresh_collection_commander_legalities(
        self,
        progress: Callable[[str], None] | None = None,
    ) -> int:
        """Fetch Scryfall legalities.commander for collection cards.

        Returns how many cards were looked up (inventory copies ∪ deck lists).
        """
        oracle_ids = self.collection_oracle_ids()
        if not oracle_ids:
            if progress is not None:
                progress("No collection cards to refresh.")
            return 0

        def report(message: str) -> None:
            if progress is not None:
                progress(message)

        total = len(oracle_ids)
        batch_size = SCRYFALL_COLLECTION_BATCH_SIZE
        for start in range(0, total, batch_size):
            chunk = oracle_ids[start : start + batch_size]
            report(
                f"Refreshing Commander legalities… "
                f"{min(start + len(chunk), total):,}/{total:,}"
            )
            identifiers = [{"oracle_id": oracle_id} for oracle_id in chunk]
            try:
                payload = self._client.fetch_cards_collection(identifiers)
            except Exception as exc:
                raise ScryfallOfflineError(
                    "Could not refresh Commander legalities from Scryfall."
                ) from exc

            data = payload.get("data")
            if not isinstance(data, list):
                continue
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                oracle_id = entry.get("oracle_id")
                if not isinstance(oracle_id, str):
                    continue
                card = self._session.get(Card, oracle_id)
                legality = commander_legality_from_payload(entry)
                if card is None:
                    self.upsert_from_payload(entry)
                    continue
                card.commander_legality = legality

            self._session.flush()

        report(f"Commander legalities refreshed for {total:,} collection cards.")
        return total
