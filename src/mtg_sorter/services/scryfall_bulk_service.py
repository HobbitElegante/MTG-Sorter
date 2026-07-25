import gzip
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_scryfall_art_series
from mtg_sorter.api.scryfall_client import ScryfallClient
from mtg_sorter.config import (
    SCRYFALL_BULK_BATCH_SIZE,
    SCRYFALL_BULK_ORACLE_TYPE,
    SCRYFALL_BULK_TYPES,
    SETTING_BULK_ORACLE_CARD_COUNT,
    SETTING_BULK_ORACLE_SYNCED_AT,
    SETTING_BULK_ORACLE_UPDATED_AT,
    SETTING_BULK_PACK_TYPE,
)
from mtg_sorter.models import Card
from mtg_sorter.repositories import CardRepository, SettingsRepository
from mtg_sorter.services.scryfall_service import card_from_scryfall


@dataclass(frozen=True)
class BulkSyncResult:
    imported_cards: int
    total_cards: int
    bulk_updated_at: str | None
    pack_type: str


@dataclass(frozen=True)
class BulkSyncStatus:
    cached_cards: int
    pack_type: str | None
    bulk_updated_at: str | None
    last_synced_at: str | None
    imported_cards: int | None
    remote_updated_at: str | None = None
    update_available: bool = False


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


def _is_newer_timestamp(remote: str | None, local: str | None) -> bool:
    if remote is None:
        return False
    if local is None:
        return True
    return remote > local


class ScryfallBulkService:
    def __init__(self, session: Session, client: ScryfallClient | None = None) -> None:
        self._session = session
        self._cards = CardRepository(session)
        self._settings = SettingsRepository(session)
        self._client = client or ScryfallClient()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def status(self, *, remote_updated_at: str | None = None) -> BulkSyncStatus:
        pack_type = self._get_setting(SETTING_BULK_PACK_TYPE)
        bulk_updated_at = self._get_setting(SETTING_BULK_ORACLE_UPDATED_AT)
        update_available = False
        if remote_updated_at is not None:
            update_available = _is_newer_timestamp(remote_updated_at, bulk_updated_at)
        return BulkSyncStatus(
            cached_cards=self._cards.count_all(),
            pack_type=pack_type,
            bulk_updated_at=bulk_updated_at,
            last_synced_at=self._get_setting(SETTING_BULK_ORACLE_SYNCED_AT),
            imported_cards=self._get_int_setting(SETTING_BULK_ORACLE_CARD_COUNT),
            remote_updated_at=remote_updated_at,
            update_available=update_available,
        )

    def remote_pack_timestamps(self) -> dict[str, str | None]:
        """Return updated_at for supported packs from /bulk-data (no file download)."""
        stamps: dict[str, str | None] = {}
        for entry in self._client.fetch_bulk_data():
            pack_type = entry.get("type")
            if pack_type not in SCRYFALL_BULK_TYPES:
                continue
            updated = entry.get("updated_at")
            stamps[str(pack_type)] = updated if isinstance(updated, str) else None
        return stamps

    def check_remote_status(self) -> BulkSyncStatus:
        """Compare local bulk timestamp to Scryfall /bulk-data (no file download)."""
        pack_type = self._get_setting(SETTING_BULK_PACK_TYPE) or SCRYFALL_BULK_ORACLE_TYPE
        try:
            stamps = self.remote_pack_timestamps()
        except Exception:
            return self.status()
        return self.status(remote_updated_at=stamps.get(pack_type))

    def sync_oracle_cards(
        self,
        progress: Callable[[str], None] | None = None,
    ) -> BulkSyncResult:
        return self.sync_bulk(SCRYFALL_BULK_ORACLE_TYPE, progress=progress)

    def sync_bulk(
        self,
        pack_type: str,
        progress: Callable[[str], None] | None = None,
    ) -> BulkSyncResult:
        if pack_type not in SCRYFALL_BULK_TYPES:
            raise ValueError(f"Unsupported bulk pack type: {pack_type}")

        def report(message: str) -> None:
            if progress is not None:
                progress(message)

        report(f"Fetching Scryfall bulk catalog ({pack_type})…")
        bulk_entry = self._find_bulk_entry(pack_type)
        download_uri = _bulk_download_uri(bulk_entry)

        bulk_updated_at = bulk_entry.get("updated_at")
        updated_at_text = (
            bulk_updated_at if isinstance(bulk_updated_at, str) else None
        )

        with NamedTemporaryFile(suffix=".bulk", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            report(f"Downloading {pack_type} bulk file…")
            self._client.download_bulk_file(download_uri, temp_path)

            imported = 0
            batch_by_id: dict[str, Card] = {}
            report("Importing cards into local cache…")
            for line_number, payload in enumerate(
                _iter_bulk_card_payloads(temp_path), start=1
            ):
                if is_scryfall_art_series(payload):
                    continue

                card = card_from_scryfall(payload)
                existing = self._cards.get(card.oracle_id)
                if existing is None:
                    pending = batch_by_id.get(card.oracle_id)
                    if pending is None:
                        batch_by_id[card.oracle_id] = card
                    else:
                        self._merge_card_fields(pending, card)
                else:
                    self._merge_card_fields(existing, card)

                imported += 1
                if len(batch_by_id) >= SCRYFALL_BULK_BATCH_SIZE:
                    self._session.add_all(batch_by_id.values())
                    self._session.flush()
                    batch_by_id.clear()
                    report(f"Imported {imported:,} cards…")

                if line_number % 5000 == 0:
                    report(f"Processed {line_number:,} lines…")

            if batch_by_id:
                self._session.add_all(batch_by_id.values())
                self._session.flush()

            removed_art_series = self._purge_orphan_art_series()

            total_cards = self._cards.count_all()
            synced_at = datetime.now(UTC).isoformat()
            self._set_setting(SETTING_BULK_PACK_TYPE, pack_type)
            self._set_setting(SETTING_BULK_ORACLE_SYNCED_AT, synced_at)
            if updated_at_text is not None:
                self._set_setting(SETTING_BULK_ORACLE_UPDATED_AT, updated_at_text)
            self._set_setting(SETTING_BULK_ORACLE_CARD_COUNT, str(imported))

            report(
                f"Sync complete — {imported:,} {pack_type} entries processed"
                f" ({removed_art_series:,} Art Series entries removed)."
            )
            return BulkSyncResult(
                imported_cards=imported,
                total_cards=total_cards,
                bulk_updated_at=updated_at_text,
                pack_type=pack_type,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    def _merge_card_fields(self, target: Card, source: Card) -> None:
        target.name = source.name
        target.mana_cost = source.mana_cost
        target.type_line = source.type_line
        target.oracle_text = source.oracle_text
        target.colors = source.colors
        target.color_identity = source.color_identity
        target.cmc = source.cmc
        if source.image_uri:
            target.image_uri = source.image_uri
        if source.image_uri_back:
            target.image_uri_back = source.image_uri_back
        target.commander_legality = source.commander_legality
        target.is_basic_land = source.is_basic_land
        target.is_token = source.is_token

    def _purge_orphan_art_series(self) -> int:
        return self._cards.purge_orphan_art_series()

    def _find_bulk_entry(self, bulk_type: str) -> dict:
        for entry in self._client.fetch_bulk_data():
            if entry.get("type") == bulk_type:
                return entry
        raise ValueError(f"Bulk type '{bulk_type}' was not found on Scryfall.")

    def _get_setting(self, key: str) -> str | None:
        return self._settings.get(key)

    def _get_int_setting(self, key: str) -> int | None:
        raw = self._get_setting(key)
        if raw is None:
            return None
        return int(raw)

    def _set_setting(self, key: str, value: str) -> None:
        self._settings.set(key, value)
