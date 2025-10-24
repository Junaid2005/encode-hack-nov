from typing import Any, Dict, List, Optional, Iterator

import requests
from requests import Response

from .config import Settings


class HyperSyncError(Exception):
    """Raised when HyperSync responds with an error or unexpected payload."""


class HyperSyncClient:
    """Thin client for Envio HyperSync /query endpoint."""

    def __init__(
        self, settings: Settings, session: Optional[requests.Session] = None
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    def query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compatibility method returning only the 'data' list."""
        payload = self._post(query)
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise HyperSyncError("HyperSync response missing 'data' list")
        return data

    def query_with_meta(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Return full payload including meta fields like next_block, archive_height, etc."""
        return self._post(query)

    def paginate(
        self, base_query: Dict[str, Any], *, max_pages: int = 10
    ) -> Iterator[Dict[str, Any]]:
        """Iterate through paginated results using next_block if present.

        This mirrors the time-window behavior described in context.txt: each response
        may include a next_block to continue from.
        """
        q = dict(base_query)
        for _ in range(max_pages):
            payload = self._post(q)
            yield payload
            next_block = payload.get("next_block") or (payload.get("meta") or {}).get(
                "next_block"
            )
            if next_block is None:
                break
            q["from_block"] = int(next_block)

    def _post(self, query: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.settings.hypersync_api_token:
            headers["Authorization"] = f"Bearer {self.settings.hypersync_api_token}"
        try:
            resp: Response = self.session.post(
                self.settings.hypersync_api_url,
                json=query,
                headers=headers,
                timeout=self.settings.request_timeout_seconds,
                verify=self.settings.request_verify_tls,
            )
        except requests.RequestException as e:
            raise HyperSyncError(f"HyperSync request error: {e}") from e

        if not resp.ok:
            text = resp.text[:500]
            raise HyperSyncError(f"HyperSync non-OK status {resp.status_code}: {text}")

        try:
            payload = resp.json()
        except ValueError as e:
            raise HyperSyncError("HyperSync returned non-JSON response") from e

        if not isinstance(payload, dict):
            raise HyperSyncError("HyperSync response must be a JSON object")
        return payload
