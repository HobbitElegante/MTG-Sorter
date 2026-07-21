from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_basic_land_type_line, is_token_type_line
from mtg_sorter.api.scryfall_client import ScryfallClient
from mtg_sorter.models import Card


def card_from_scryfall(payload: dict[str, Any]) -> Card:
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


class ScryfallService:
    def __init__(self, session: Session, client: ScryfallClient | None = None) -> None:
        self._session = session
        self._client = client or ScryfallClient()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_and_cache(self, name: str) -> Card:
        cached = self._session.scalar(
            select(Card).where(Card.name.ilike(name)).limit(1)
        )
        if cached is not None:
            return cached

        payload = self._client.fetch_card_fuzzy(name)
        card = self._session.get(Card, payload["oracle_id"])
        if card is None:
            card = card_from_scryfall(payload)
            self._session.add(card)
            self._session.flush()
        return card
