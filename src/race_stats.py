"""
Per-race statistics for the calendar: how many ran, and who was on the podium.

This reads ``points_<oris_id>.csv`` — the per-race files the results calculator
writes — and is deliberately separate from :mod:`src.results`, which reads the
``overall_*.csv`` season standings. Different input, different page, different
lifecycle: a season's standings are rewritten every time a race is added, while
a race's own results are written once and then never change.

Nothing here raises. The calendar must render even if a results file is
missing, truncated or hand-edited into nonsense, because the stats are an
enrichment of a page whose real job is telling people when the next race is.
"""

import csv
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from results_calculator.overall import CATEGORIES
from src.paths import RACE_RESULTS_GLOB, results_dir

logger = logging.getLogger(__name__)

#: Columns this module needs. Naming them rather than pinning a column count
#: means the 7-column files committed before the Sex column was added and the
#: 8-column files written since both parse, and so will a ninth column.
REQUIRED_COLUMNS: Final = frozenset({"ClassDesc", "Place", "Name", "Time"})

#: Placings that are not a placing. DISK is a disqualification, MS is "mimo
#: soutěž" - ran, but out of competition. Both score zero and neither belongs
#: on a podium, and both are excluded simply by failing to parse as a number.
PODIUM_SIZE: Final = 3

#: How many seasons of parsed results to hold. Four seasons exist; a couple of
#: spare slots absorb a results file being edited while the site is running.
_CACHE_SIZE: Final = 8


@dataclass(frozen=True)
class PodiumEntry:
    """One runner on a race's podium."""

    place: int
    name: str
    time: str


@dataclass(frozen=True)
class RaceStats:
    """
    What is known about one finished race.

    Attributes
    ----------
    oris_id
        The race's ORIS id, which is also what names its results file.
    participants
        Everyone in the results file: every category, including runners who
        were disqualified or ran out of competition. It answers "how big was
        this race", which is the question the number on the calendar is
        standing in for.
    podium
        Category to its first three placings, in :data:`CATEGORIES` order.
        A category nobody entered is absent rather than empty.
    category_counts
        How many ran in each category on the podium, for the same keys.

    """

    oris_id: int
    participants: int
    podium: dict[str, list[PodiumEntry]]
    category_counts: dict[str, int]


def _place_number(place: str) -> int | None:
    """
    Parse ``"3."`` into ``3``.

    Returns ``None`` for anything that is not a placing, which is how DISK and
    MS rows are kept off the podium without naming them.
    """
    try:
        return int(place.strip().rstrip("."))
    except (AttributeError, ValueError):
        return None


def _podium_from(rows: list[dict[str, str]]) -> list[PodiumEntry]:
    """
    Pick the first three placings out of one category's rows.

    The ``Place`` column is already standard competition ranking - the timing
    software applied it before ORIS ever saw the results - so ties need no
    special handling here: a shared first place is simply two rows numbered 1
    followed by a row numbered 3, and taking everything up to third place
    returns all of them.
    """
    placed = []
    for row in rows:
        place = _place_number(row.get("Place", ""))
        if place is not None and place <= PODIUM_SIZE:
            placed.append(
                PodiumEntry(
                    place=place,
                    name=(row.get("Name") or "").strip(),
                    time=(row.get("Time") or "").strip(),
                )
            )
    placed.sort(key=lambda entry: entry.place)
    return placed


def _read_race_file(path: Path, oris_id: int) -> RaceStats | None:
    """Read one ``points_*.csv``. Returns ``None`` if it cannot be used."""
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(
                reader.fieldnames
            ):
                logger.error("%s is missing columns this needs; skipping it.", path)
                return None
            rows = list(reader)
    except (OSError, ValueError, csv.Error) as e:
        logger.error("Could not read %s: %s", path, e)
        return None

    if not rows:
        return None

    by_category: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_category.setdefault((row.get("ClassDesc") or "").strip(), []).append(row)

    podium = {}
    counts = {}
    for category in CATEGORIES:
        # Only the five BZL categories. A race can also carry classes the
        # league does not score - "Expert H", and the "ZV-other" bucket for
        # entrants outside the Z and V age windows. ZV-other must be left out
        # on correctness grounds rather than taste: its Place values are the
        # placings of the whole ZV field, so its "1." is not a winner of
        # anything.
        rows_in_category = by_category.get(category, [])
        entries = _podium_from(rows_in_category)
        if entries:
            podium[category] = entries
            counts[category] = len(rows_in_category)

    return RaceStats(
        oris_id=oris_id,
        participants=len(rows),
        podium=podium,
        category_counts=counts,
    )


def _signature(directory: Path) -> tuple[tuple[str, int, int], ...]:
    """
    Describe the results files well enough to notice any change to them.

    Used as part of the cache key. ``data/`` is a mounted volume, so publishing
    a new race is a file appearing under a running container - without this the
    parsed results would be stale until the process restarted. Size is included
    alongside the modification time because some mounted filesystems report
    coarse timestamps.
    """
    try:
        entries = []
        with os.scandir(directory) as it:
            for entry in it:
                if not entry.name.startswith("points_") or not entry.name.endswith(
                    ".csv"
                ):
                    continue
                stat = entry.stat()
                entries.append((entry.name, stat.st_mtime_ns, stat.st_size))
        return tuple(sorted(entries))
    except OSError:
        return ()


@lru_cache(maxsize=_CACHE_SIZE)
def _load(
    season: str, signature: tuple[tuple[str, int, int], ...]
) -> dict[int, RaceStats]:
    """Parse every results file in a season. Cached against the signature."""
    stats = {}
    for path in sorted(results_dir(season).glob(RACE_RESULTS_GLOB)):
        try:
            oris_id = int(path.stem.removeprefix("points_"))
        except ValueError:
            logger.warning("Ignoring %s: no ORIS id in the file name.", path)
            continue
        race = _read_race_file(path, oris_id)
        if race is not None:
            stats[oris_id] = race
    return stats


def load_race_stats(season: str) -> dict[int, RaceStats]:
    """
    Return the statistics of every race in a season that has published results.

    Parameters
    ----------
    season
        Season identifier, e.g. ``"25-26"``.

    Returns
    -------
    ORIS id to :class:`RaceStats`, empty if the season has no results yet. The
    objects are shared out of a cache and must not be modified.

    """
    return _load(season, _signature(results_dir(season)))


def race_stats_by_event(
    season: str, events: Mapping[str, Mapping[str, Any]]
) -> dict[str, RaceStats]:
    """
    Re-key a season's race statistics by event id, for the calendar.

    Parameters
    ----------
    season
        Season identifier, e.g. ``"25-26"``.
    events
        The season's events as the calendar view has them, keyed by event id.

    Returns
    -------
    Event id to :class:`RaceStats`, holding only the events that have a results
    file. An event with no ORIS id, or one whose race has not been published
    yet, is simply absent - the calendar then shows that race without any
    statistics, which is the intended behaviour and not an error worth naming
    on the page.

    """
    stats = load_race_stats(season)
    by_event = {}
    for event_id, event in events.items():
        oris_id = event.get("oris_id")
        if oris_id is not None and oris_id in stats:
            by_event[event_id] = stats[oris_id]
    return by_event
