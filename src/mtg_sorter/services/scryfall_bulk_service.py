import gzip
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mtg_sorter.api.scryfall_client import ScryfallClient
from mtg_sorter.config import (
    SCRYFALL_BULK_BATCH_SIZE,
    SCRYFALL_BULK_ORACLE_TYPE,
    SETTING_BULK_ORACLE_CARD_COUNT,
    SETTING_BULK_ORACLE_SYNCED_AT,
    SETTING_BULK_ORACLE_UPDATED_AT,
)
from mtg_sorter.models import AppSetting, Card
from mtg_sorter.services.scryfall_service import card_from_scryfall


@dataclass(frozen=True)
class BulkSyncResult:
    imported_cards: int
    total_cards: int
    bulk_updated_at: str | None


@dataclass(frozen=True)
class BulkSyncStatus:
    cached_cards: int
    bulk_updated_at: str | None
    last_synced_at: str | None
    imported_cards: int | None


def _iter_bulk_card_payloads(path: Path):
    with path.open("rb") as raw:
        header = raw.read(2)

    if header == b"\x1f\x8b":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)
        return

    text = path.read_text(encoding="utf-8").lstrip()
    if text.startswith("["):
        for payload in json.loads(text):
            if isinstance(payload, dict):
                yield payload
        return

    for line in text.splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def _bulk_download_uri(bulk_entry: dict) -> str:
    jsonl_uri = bulk_entry.get("jsonl_download_uri")
    if isinstance(jsonl_uri, str):
        return jsonl_uri

    download_uri = bulk_entry.get("download_uri")
    if isinstance(download_uri, str):
        return download_uri

    raise ValueError("Scryfall bulk entry is missing a download URI")


class ScryfallBulkService:
    def __init__(self, session: Session, client: ScryfallClient | None = None) -> None:
        self._session = session
        self._client = client or ScryfallClient()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def status(self) -> BulkSyncStatus:
        return BulkSyncStatus(
            cached_cards=int(
                self._session.scalar(select(func.count()).select_from(Card)) or 0
            ),
            bulk_updated_at=self._get_setting(SETTING_BULK_ORACLE_UPDATED_AT),
            last_synced_at=self._get_setting(SETTING_BULK_ORACLE_SYNCED_AT),
            imported_cards=self._get_int_setting(SETTING_BULK_ORACLE_CARD_COUNT),
        )

    def sync_oracle_cards(
        self,
        progress: Callable[[str], None] | None = None,
    ) -> BulkSyncResult:
        def report(message: str) -> None:
            if progress is not None:
                progress(message)

        report("Fetching Scryfall bulk catalog…")
        bulk_entry = self._find_bulk_entry(SCRYFALL_BULK_ORACLE_TYPE)
        download_uri = _bulk_download_uri(bulk_entry)

        bulk_updated_at = bulk_entry.get("updated_at")
        updated_at_text = (
            bulk_updated_at if isinstance(bulk_updated_at, str) else None
        )

        with NamedTemporaryFile(suffix=".bulk", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            report("Downloading oracle-cards bulk file…")
            self._client.download_bulk_file(download_uri, temp_path)

            imported = 0
            batch: list[Card] = []
            report("Importing cards into local cache…")
            for line_number, payload in enumerate(
                _iter_bulk_card_payloads(temp_path), start=1
            ):
                card = card_from_scryfall(payload)
                existing = self._session.get(Card, card.oracle_id)
                if existing is None:
                    batch.append(card)
                else:
                    existing.name = card.name
                    existing.mana_cost = card.mana_cost
                    existing.type_line = card.type_line
                    existing.oracle_text = card.oracle_text
                    existing.colors = card.colors
                    existing.color_identity = card.color_identity
                    existing.cmc = card.cmc
                    existing.image_uri = card.image_uri
                    existing.is_basic_land = card.is_basic_land
                    existing.is_token = card.is_token

                imported += 1
                if len(batch) >= SCRYFALL_BULK_BATCH_SIZE:
                    self._session.add_all(batch)
                    self._session.flush()
                    batch.clear()
                    report(f"Imported {imported:,} cards…")

                if line_number % 5000 == 0:
                    report(f"Processed {line_number:,} lines…")

            if batch:
                self._session.add_all(batch)
                self._session.flush()

            total_cards = int(
                self._session.scalar(select(func.count()).select_from(Card)) or 0
            )
            synced_at = datetime.now(UTC).isoformat()
            self._set_setting(SETTING_BULK_ORACLE_SYNCED_AT, synced_at)
            if updated_at_text is not None:
                self._set_setting(SETTING_BULK_ORACLE_UPDATED_AT, updated_at_text)
            self._set_setting(SETTING_BULK_ORACLE_CARD_COUNT, str(imported))

            report(f"Sync complete — {imported:,} oracle cards processed.")
            return BulkSyncResult(
                imported_cards=imported,
                total_cards=total_cards,
                bulk_updated_at=updated_at_text,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    def _find_bulk_entry(self, bulk_type: str) -> dict:
        for entry in self._client.fetch_bulk_data():
            if entry.get("type") == bulk_type:
                return entry
        raise ValueError(f"Bulk type '{bulk_type}' was not found on Scryfall.")

    def _get_setting(self, key: str) -> str | None:
        value = self._session.get(AppSetting, key)
        return value.value if value is not None else None

    def _get_int_setting(self, key: str) -> int | None:
        raw = self._get_setting(key)
        if raw is None:
            return None
        return int(raw)

    def _set_setting(self, key: str, value: str) -> None:
        setting = self._session.get(AppSetting, key)
        if setting is None:
            setting = AppSetting(key=key, value=value)
            self._session.add(setting)
        else:
            setting.value = value
        self._session.flush()
