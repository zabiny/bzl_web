"""Loads the per-season event configs and keeps them refreshed from ORIS."""

import json
import logging
import re
from typing import Any, overload

from src.event import Event
from src.oris import OrisClient
from src.paths import data_dir

logger = logging.getLogger(__name__)

#: A season directory is named like "25-26".
SEASON_PATTERN = re.compile(r"^\d{2}-\d{2}$")


class EventManager:
    """
    Manages loading and accessing orienteering events across multiple seasons.

    Construction never touches the network: events are loaded from their JSON
    configs plus whatever the ORIS cache already holds, so the web app always
    starts even when ORIS is down. Fresh data arrives via :meth:`update`, which
    the app schedules in the background.

    Attributes
    ----------
    _events
        Dictionary mapping season identifiers to their events.

    """

    def __init__(self, oris_client: OrisClient | None = None) -> None:
        """
        Initialize the EventManager and load all events from all seasons.

        Parameters
        ----------
        oris_client
            Client used to enrich events with ORIS data. A default one is
            created if not supplied.

        """
        self._oris = oris_client if oris_client is not None else OrisClient()
        self._events: dict[str, dict[str, Event]] = {}
        self.update(use_network=False)

    def update(self, use_network: bool = True) -> None:
        """
        Reload every season from disk and refresh it from ORIS.

        Check for changes in the data folder and, unless ``use_network`` is
        false, fetch current data from the ORIS API.

        Parameters
        ----------
        use_network
            Whether ORIS may be contacted. ``False`` answers from the cache only.

        """
        try:
            self._events = {
                season: self._load_all_events(season, use_network=use_network)
                for season in self.get_all_seasons()
            }
        except Exception:
            # This runs on a background scheduler thread; an exception escaping
            # here would kill the refresh job and leave the site frozen on old
            # data with no indication why.
            logger.exception(
                "Refreshing events failed; keeping previously loaded data."
            )

    def _load_all_events(
        self, season: str, use_network: bool = True
    ) -> dict[str, Event]:
        """
        Create a dict with all events of a season.

        Parameters
        ----------
        season
            season string (e.g. "22-23")
        use_network
            Whether ORIS may be contacted.

        Returns
        -------
        Dict
            All events in a season. 'event_id' (NOT oris_id) as keys, events as
            values. Sorted by event date, undated events last.
        """
        season_dir = data_dir() / season / "events"
        events = {}

        for event_file in sorted(season_dir.glob("*.json")):
            event = self._create_event_from_config(
                season, event_file.stem, use_network=use_network
            )
            if event:
                events[event_file.stem] = event

        def _sort_key(item: tuple[str, Event]) -> tuple[bool, Any]:
            # Events whose date is still unknown sort last instead of raising.
            date = item[1].date
            return (date is None, date)

        events = dict(sorted(events.items(), key=_sort_key))
        return self._assign_bzl_order(events)

    def _create_event_from_config(
        self, season: str, event_id: str, use_network: bool = True
    ) -> Event | None:
        """
        Load event config, enrich it with ORIS data, and create an Event.

        Parameters
        ----------
        season
            Season to which the event belongs (e.g. '21-22')
        event_id
            Event identifier in the season (e.g. 'nopb'). It must be unique within
            the season. Config for the event must be stored in
            'data/{season}/events/{event_id}.json' file.
        use_network
            Whether ORIS may be contacted.

        Returns
        -------
        instance of an Event class, or None if the config is unusable
        """
        config_path = data_dir() / season / "events" / f"{event_id}.json"
        try:
            with config_path.open(encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            logger.error("Config file: %s was not found!", config_path)
            return None
        except (OSError, ValueError) as e:
            logger.error("Config file %s could not be read: %s", config_path, e)
            return None

        try:
            event = Event(**config)
        except (TypeError, ValueError) as e:
            logger.error("Event initialization failed!\nConfig: %s\n%s", config, e)
            return None

        if event.oris_id:
            oris_data = self._oris.get_event(event.oris_id, use_network=use_network)
            if oris_data is not None:
                event.apply_oris_data(oris_data)
            if not event.web:
                event.web = f"https://oris.orientacnisporty.cz/Zavod?id={event.oris_id}"

        if not event.name and not event.date:
            # With neither local metadata nor anything from ORIS there is
            # nothing to show. During the offline start-up pass this is an
            # expected, temporary state: the background refresh fills it in.
            if event.oris_id and not use_network:
                logger.info(
                    "Event %s has no local name/date and nothing cached from "
                    "ORIS yet; it will appear after the next refresh.",
                    event_id,
                )
            else:
                logger.error(
                    "Each event must have either 'oris_id' or both 'name' and "
                    "'date'. Event %s has neither.",
                    event_id,
                )
            return None
        return event

    def get_event(self, season: str, event_id: str) -> Event | None:
        """
        Get event from loaded events by season and event_id.

        Parameters
        ----------
        season
            Season to which the event belongs (e.g. '21-22')
        event_id
            Event identifier in the season (e.g. 'nopb'). It must be unique within
            the season. Config for the event must be stored in
            'data/{season}/events/{event_id}.json' file.

        Returns
        -------
        The event, or None if the season or the event does not exist.
        """
        return self._events.get(season, {}).get(event_id)

    @overload
    def get_all_events(self, season: str) -> dict[str, Event] | None: ...

    @overload
    def get_all_events(
        self, season: str, as_dicts: bool = False
    ) -> dict[str, dict[str, Any]] | None: ...

    def get_all_events(
        self, season: str, as_dicts: bool = False
    ) -> dict[str, Event] | dict[str, dict[str, Any]] | None:
        """
        Get all events of a season.

        Parameters
        ----------
        season
            season string (e.g. "22-23")
        as_dicts
            return events as dicts (not Event classes)

        Returns
        -------
        Dict
            All events in a season. 'event_id' (NOT oris_id) as keys, events as
            values. Sorted by event date. None if the season is unknown.
        """
        events = self._events.get(season)
        if events is None:
            return None
        if as_dicts:
            return {e_id: e.to_dict() for e_id, e in events.items()}
        return events

    def _assign_bzl_order(self, events: dict[str, Event]) -> dict[str, Event]:
        """Assign each BZL race of a season its running number, in date order."""
        bzl_count = 0
        for event in events.values():
            if event.is_bzl:
                bzl_count += 1
                event.bzl_order = bzl_count
        return events

    def get_all_seasons(self) -> list[str]:
        """
        Get a sorted list of all available seasons.

        Returns
        -------
        List of season identifiers, oldest first (e.g., ['24-25', '25-26']).

        """
        root = data_dir()
        if not root.is_dir():
            logger.error("Data directory %s does not exist.", root)
            return []
        return sorted(
            p.name
            for p in root.iterdir()
            if p.is_dir() and SEASON_PATTERN.match(p.name)
        )

    def get_latest_season(self) -> str | None:
        """
        Get the most recent season.

        Returns
        -------
        The newest season identifier, or None when there are no seasons. Used so
        that the navigation does not have to hard-code the current season.

        """
        seasons = self.get_all_seasons()
        return seasons[-1] if seasons else None

    def season_exists(self, season: str) -> bool:
        """Return whether the given season has been loaded."""
        return season in self._events

    def count_bzl_races(self, season: str) -> int:
        """Return how many races of a season count towards the BZL standings."""
        events = self._events.get(season, {})
        return sum(1 for e in events.values() if e.is_bzl)
