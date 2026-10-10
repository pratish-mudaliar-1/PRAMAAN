"""app/adapters/http_rest.py — HTTP REST implementations of external data adapters.

Features:
  - SSRF Protection: blocks loopback, cloud metadata (169.254.169.254), and private IP ranges unless explicitly overridden.
  - Privacy Enforcement: scans all JSON payloads and rejects prohibited PII fields (name, aadhaar, pan, etc.).
  - Resilient HTTP: uses httpx.AsyncClient with timeouts and bearer token auth support.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.csv_file import _PROHIBITED_FIELDS
from app.adapters.interfaces import (
    AggregateCount,
    AttendanceSource,
    InventoryItem,
    InventorySource,
    TimetableEntry,
    TimetableSource,
    TrainerAttendanceSource,
    TrainerCount,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_url_ssrf_safe(url: str, *, allow_private: bool = False) -> None:
    """Validate that a URL is safe against SSRF attacks."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'; only http/https allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Missing hostname in URL")

    if allow_private:
        return

    # Check for direct IP address or resolve hostname
    try:
        ip = ipaddress.ip_address(hostname)
        ips = [ip]
    except ValueError:
        try:
            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, None)
            ips = [ipaddress.ip_address(addr[4][0]) for addr in addr_info]
        except Exception as exc:
            raise ValueError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    for addr in ips:
        if addr.is_loopback:
            raise ValueError(f"Loopback IP '{addr}' is prohibited for SSRF protection")
        if addr.is_private:
            raise ValueError(f"Private IP '{addr}' is prohibited for SSRF protection")
        if addr.is_link_local or addr.is_reserved or addr.is_multicast:
            raise ValueError(f"Restricted IP '{addr}' is prohibited for SSRF protection")


def _check_prohibited_json(obj: Any, source: str) -> None:
    """Recursively check that no prohibited PII fields exist in API responses."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in _PROHIBITED_FIELDS:
                raise ValueError(
                    f"HTTP response from '{source}' contains prohibited field '{k}'. "
                    "Per DATA_CONTRACT.md, no personal identifiers may be present."
                )
            _check_prohibited_json(v, source)
    elif isinstance(obj, list):
        for item in obj:
            _check_prohibited_json(item, source)


def _parse_dt(val: str) -> datetime:
    """Parse ISO8601 datetime string and ensure UTC timezone."""
    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class HttpAttendanceSource(AttendanceSource):
    """Fetches aggregate attendance counts from an external REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        allow_private: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        validate_url_ssrf_safe(base_url, allow_private=allow_private)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allow_private = allow_private
        self._timeout = timeout_seconds

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_claimed_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[AggregateCount]:
        url = f"{self._base_url}/attendance"
        params = {
            "batch_id": batch_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()

        _check_prohibited_json(data, url)

        results: list[AggregateCount] = []
        for item in data.get("items", data if isinstance(data, list) else []):
            results.append(
                AggregateCount(
                    batch_id=item["batch_id"],
                    session_ref=item["session_ref"],
                    claimed_count=int(item["claimed_count"]),
                    source_ref=item.get("source_ref"),
                )
            )
        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.get(f"{self._base_url}/healthz", headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            return False


class HttpTimetableSource(TimetableSource):
    """Fetches timetable scheduled sessions from an external REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        allow_private: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        validate_url_ssrf_safe(base_url, allow_private=allow_private)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allow_private = allow_private
        self._timeout = timeout_seconds

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_sessions(
        self, centre_code: str, from_date: datetime, to_date: datetime
    ) -> list[TimetableEntry]:
        url = f"{self._base_url}/timetable"
        params = {
            "centre_code": centre_code,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()

        _check_prohibited_json(data, url)

        results: list[TimetableEntry] = []
        for item in data.get("items", data if isinstance(data, list) else []):
            results.append(
                TimetableEntry(
                    batch_id=item["batch_id"],
                    zone_code=item["zone_code"],
                    scheduled_start=_parse_dt(item["scheduled_start"]),
                    scheduled_end=_parse_dt(item["scheduled_end"]),
                    trade_code=item.get("trade_code"),
                    source_ref=item.get("source_ref"),
                )
            )
        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.get(f"{self._base_url}/healthz", headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            return False


class HttpInventorySource(InventorySource):
    """Fetches sanctioned infrastructure items from an external REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        allow_private: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        validate_url_ssrf_safe(base_url, allow_private=allow_private)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allow_private = allow_private
        self._timeout = timeout_seconds

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_inventory(self, centre_code: str) -> list[InventoryItem]:
        url = f"{self._base_url}/inventory/{centre_code}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()

        _check_prohibited_json(data, url)

        results: list[InventoryItem] = []
        for item in data.get("items", data if isinstance(data, list) else []):
            results.append(
                InventoryItem(
                    centre_code=centre_code,
                    zone_code=item["zone_code"],
                    item_class=item["item_class"],
                    sanctioned_count=int(item["sanctioned_count"]),
                    critical=bool(item.get("critical", False)),
                    source_ref=item.get("source_ref"),
                )
            )
        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.get(f"{self._base_url}/healthz", headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            return False


class HttpTrainerAttendanceSource(TrainerAttendanceSource):
    """Fetches aggregate trainer attendance counts from an external REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        allow_private: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        validate_url_ssrf_safe(base_url, allow_private=allow_private)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allow_private = allow_private
        self._timeout = timeout_seconds

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_trainer_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[TrainerCount]:
        url = f"{self._base_url}/trainer-attendance"
        params = {
            "batch_id": batch_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()

        _check_prohibited_json(data, url)

        results: list[TrainerCount] = []
        for item in data.get("items", data if isinstance(data, list) else []):
            results.append(
                TrainerCount(
                    batch_id=item["batch_id"],
                    session_ref=item["session_ref"],
                    trainer_count=int(item["trainer_count"]),
                    source_ref=item.get("source_ref"),
                )
            )
        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.get(f"{self._base_url}/healthz", headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            return False
