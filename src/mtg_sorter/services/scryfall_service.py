import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_basic_land_type_line, is_token_type_line
from mtg_sorter.api.scryfall_client import ScryfallClient
from mtg_sorter.models import Card


def normalize_card_name(name: str) -> str:
    lowered = name.casefold().strip()
    return re.sub(r"[^a-z0-9]+", "", lowered)


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

    def lookup_local(self, name: str) -> Card | None:
        trimmed = name.strip()
        if not trimmed:
            return None

        exact = self._session.scalar(
            select(Card).where(func.lower(Card.name) == trimmed.casefold()).limit(1)
        )
        if exact is not None:
            return exact

        normalized_query = normalize_card_name(trimmed)
        if normalized_query:
            for card in self._session.scalars(select(Card)).all():
                if normalize_card_name(card.name) == normalized_query:
                    return card

        fuzzy_matches = list(
            self._session.scalars(
                select(Card).where(Card.name.ilike(f"%{trimmed}%")).limit(5)
            ).all()
        )
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]

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
            card.is_basic_land = refreshed.is_basic_land
            card.is_token = refreshed.is_token
        self._session.flush()
        return card

    def fetch_and_cache(self, name: str) -> Card:
        cached = self.lookup_local(name)
        if cached is not None:
            return cached

        try:
            payload = self._client.fetch_card_fuzzy(name)
        except Exception as exc:
            raise ScryfallOfflineError(
                f"Card '{name}' is not cached locally and Scryfall is unavailable."
            ) from exc

        return self.upsert_from_payload(payload)

    def cached_card_count(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(Card)) or 0)
