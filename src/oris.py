"""
Client for the ORIS API with an on-disk fallback cache.

ORIS (https://oris.orientacnisporty.cz) is the Czech orienteering event database.
This module is the single place that talks to it from the web app.

Two properties matter here, because the whole website used to go down whenever
ORIS did:

* **Never raise.** Every network problem is caught and turned into ``None``.
* **Never re-fetch what cannot change.** Results of an event that already
  happened are frozen, so a season that is over costs zero requests.
"""

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Final

import requests

from src.paths import data_dir

logger = logging.getLogger(__name__)

API_URL: Final = "https://oris.orientacnisporty.cz/API/"

#: (connect, read) timeout in seconds. Without this a hung ORIS blocks a worker.
DEFAULT_TIMEOUT: Final = (3.05, 10.0)

#: How long after an event we keep refreshing it. Once an event is this many
#: days in the past, nothing about it can change, so we serve it from cache
#: forever and never call ORIS again.
FREEZE_AFTER_DAYS: Final = 2

CACHE_DIR_NAME: Final = ".oris_cache"


def _without_timestamp(data: dict[str, Any]) -> dict[str, Any]:
    """Return the payload without its bookkeeping timestamp, for comparison."""
    return {k: v for k, v in data.items() if k != "_cached_at"}


def _cache_dir() -> Path:
    """Return the cache directory, overridable with ``BZL_ORIS_CACHE_DIR``."""
    override = os.environ.get("BZL_ORIS_CACHE_DIR")
    return Path(override) if override else data_dir() / CACHE_DIR_NAME


class OrisClient:
    """
    Fetches event metadata from ORIS, falling back to a local cache.

    Parameters
    ----------
    cache_dir
        Directory holding the cached responses. Defaults to ``data/.oris_cache``
        (overridable with the ``BZL_ORIS_CACHE_DIR`` environment variable).
    timeout
        ``(connect, read)`` timeout passed to :mod:`requests`.

    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else _cache_dir()
        self.timeout = timeout
        self._session = requests.Session()

    def get_event(
        self, oris_id: int, *, use_network: bool = True
    ) -> dict[str, Any] | None:
        """
        Get metadata for one ORIS event.

        Parameters
        ----------
        oris_id
            Event's ORIS ID.
        use_network
            If ``False``, answer from the cache only and never make a request.
            Used at start-up so that booting the app cannot block on ORIS.

        Returns
        -------
        Normalised event data, or ``None`` if the event is neither cached nor
        reachable. Never raises.

        """
        cached = self._read_cache(oris_id)

        if not use_network:
            return cached

        # An event that is safely in the past can never change again.
        if cached is not None and self._is_frozen(cached):
            return cached

        fetched = self._fetch(oris_id)
        if fetched is not None:
            self._write_cache(oris_id, fetched)
            return fetched

        if cached is not None:
            logger.warning(
                "ORIS unreachable for event %s, serving cached data from %s.",
                oris_id,
                cached.get("_cached_at", "unknown time"),
            )
        return cached

    @staticmethod
    def _is_frozen(data: dict[str, Any]) -> bool:
        """Return whether the event is far enough in the past to stop refreshing."""
        event_date = data.get("date")
        if not isinstance(event_date, datetime.date):
            return False
        cutoff = datetime.date.today() - datetime.timedelta(days=FREEZE_AFTER_DAYS)
        return event_date < cutoff

    def _fetch(self, oris_id: int) -> dict[str, Any] | None:
        """Call the ORIS API. Returns ``None`` on any failure."""
        try:
            params: dict[str, str] = {
                "format": "json",
                "method": "getEvent",
                "id": str(oris_id),
            }
            response = self._session.get(API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as e:
            # The base class of every exception requests raises, including
            # ConnectionError, Timeout, SSLError and HTTPError. Catching the
            # same-named builtins instead would catch none of them.
            logger.error("Communication with ORIS (event %s) failed: %s", oris_id, e)
            return None
        except ValueError as e:  # malformed JSON
            logger.error("ORIS returned invalid JSON for event %s: %s", oris_id, e)
            return None

        if payload.get("Status") != "OK":
            logger.error(
                "ORIS reported an error for event %s: %s",
                oris_id,
                payload.get("Message", payload.get("Status")),
            )
            return None

        return self._normalise(payload.get("Data") or {}, oris_id)

    @staticmethod
    def _normalise(raw: dict[str, Any], oris_id: int) -> dict[str, Any] | None:
        """Pick the fields we use out of an ORIS payload and coerce their types."""

        def blank_to_none(value: Any) -> Any:
            if value is None:
                return None
            text = str(value).strip()
            # ORIS uses "0" and "" for "not set" in the GPS fields.
            return None if text in {"", "0"} else text

        raw_date = blank_to_none(raw.get("Date"))
        event_date: datetime.date | None = None
        if raw_date is not None:
            try:
                event_date = datetime.date.fromisoformat(raw_date)
            except ValueError:
                logger.warning(
                    "ORIS event %s has an unparseable date %r.", oris_id, raw_date
                )

        organizer = raw.get("Org1")
        organizer_name = (
            blank_to_none(organizer.get("Name"))
            if isinstance(organizer, dict)
            else None
        )

        return {
            "name": blank_to_none(raw.get("Name")),
            "date": event_date,
            "entry_date": blank_to_none(raw.get("EntryDate1")),
            "place_desc": blank_to_none(raw.get("Place")),
            "gps_lat": blank_to_none(raw.get("GPSLat")),
            "gps_lon": blank_to_none(raw.get("GPSLon")),
            "organizer": organizer_name,
            "_cached_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }

    def _cache_path(self, oris_id: int) -> Path:
        return self.cache_dir / f"{oris_id}.json"

    def _read_cache(self, oris_id: int) -> dict[str, Any] | None:
        """Read cached data for an event, or ``None`` if unusable."""
        path = self._cache_path(oris_id)
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            logger.warning("Could not read ORIS cache %s: %s", path, e)
            return None

        if not isinstance(data, dict):
            return None

        raw_date = data.get("date")
        if isinstance(raw_date, str):
            try:
                data["date"] = datetime.date.fromisoformat(raw_date)
            except ValueError:
                data["date"] = None
        return data

    def _write_cache(self, oris_id: int, data: dict[str, Any]) -> None:
        """
        Write event data to the cache. Cache failures are never fatal.

        A write is skipped when nothing but the timestamp would change, so a
        cache that is kept in version control does not churn on every refresh.
        """
        path = self._cache_path(oris_id)
        existing = self._read_cache(oris_id)
        if existing is not None and _without_timestamp(existing) == _without_timestamp(
            data
        ):
            return
        serialisable = dict(data)
        if isinstance(serialisable.get("date"), datetime.date):
            serialisable["date"] = serialisable["date"].isoformat()
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Write to a temporary file first so a crash mid-write cannot leave
            # a truncated cache entry behind.
            tmp_path = path.with_suffix(".json.tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(serialisable, f, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
        except OSError as e:
            logger.warning("Could not write ORIS cache %s: %s", path, e)
