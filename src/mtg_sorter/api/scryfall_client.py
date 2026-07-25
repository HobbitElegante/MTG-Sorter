import time
from pathlib import Path
from typing import Any

import httpx

from mtg_sorter.config import SCRYFALL_API_BASE, SCRYFALL_RATE_LIMIT_SECONDS


class ScryfallClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=SCRYFALL_API_BASE,
            headers={"User-Agent": "MTG-Sorter/0.5"},
            timeout=30.0,
        )
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < SCRYFALL_RATE_LIMIT_SECONDS:
            time.sleep(SCRYFALL_RATE_LIMIT_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        response = self._client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Scryfall response shape")
        return payload

    def fetch_card_by_name(self, name: str) -> dict[str, Any]:
        return self._get("/cards/named", params={"exact": name})

    def fetch_card_fuzzy(self, name: str) -> dict[str, Any]:
        return self._get("/cards/named", params={"fuzzy": name})

    def fetch_cards_collection(
        self, identifiers: list[dict[str, str]]
    ) -> dict[str, Any]:
        """POST /cards/collection (max 75 identifiers per Scryfall request)."""
        self._throttle()
        response = self._client.post("/cards/collection", json={"identifiers": identifiers})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Scryfall collection response shape")
        return payload

    def fetch_bulk_data(self) -> list[dict[str, Any]]:
        payload = self._get("/bulk-data")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("Unexpected Scryfall bulk-data response shape")
        return data

    def download_file(self, url: str, destination: Path) -> None:
        """Download any URL (API or absolute CDN) to disk with rate limiting."""
        self._throttle()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

    def download_bulk_file(self, download_uri: str, destination: Path) -> None:
        self.download_file(download_uri, destination)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ScryfallClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
