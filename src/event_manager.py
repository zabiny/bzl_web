import json
import logging  # TODO: setup logger properly
from pathlib import Path
from typing import Any, Dict, Optional, Union, overload, List
from urllib.error import HTTPError

from src.event import Event


class EventManager:
    def __init__(self) -> None:
        seasons = self.get_all_seasons()
        self._events = {season: self._load_all_events(season) for season in seasons}

    def _load_all_events(self, season: str):
        """Create a dict with all events of a season.

        Parameters
        ----------
        season
            season string (e.g. "22-23")

        Returns
        -------
        Dict
            All events in a season. 'event_id' (NOT oris_id) as keys, events as values.
            Sorted by event date.
        """
        season_dir = Path(f"data/{season}/events/")
        events = {}

        for event_file in season_dir.glob("*.json"):
            event = self._create_event_from_config(season, event_file.stem)
            if event:
                events[event_file.stem] = event

        # Sort by date
        def _event_date(event_tuple):
            # Helper function for sorting by date - class version
            return event_tuple[1].date

        events = dict(sorted(events.items(), key=_event_date))
        events = self._assign_bzl_order(events)
        return events

    def update(self) -> None:
        """Update EventManager.

        Check for changes in 'data' folder + fetch data from ORIS API.
        """
        seasons = self.get_all_seasons()
        self._events = {season: self._load_all_events(season) for season in seasons}

    def _create_event_from_config(self, season: str, event_id: str) -> Optional[Event]:
        """Load a json config with event's definition, fetch info from ORIS if there is
        an 'oris_id' in the config and create an instance of an Event class.

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
        instance of an Event class
        """
        # Load event config from file
        config_path = Path(f"data/{season}/events/{event_id}.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            logging.error(f"Config file: {config_path} was not found!")
            return None

        # Construct the Event instance
        try:
            event = Event(**config)
        except TypeError as e:
            logging.error(f"Event initialization failed!\nConfig: {config}\n{e}")
            return None

        # Add information from ORIS
        if event.oris_id:
            try:
                event.add_oris_data()
            except AttributeError as e:
                logging.error(f"Event should have oris_id, but hasn't!\n{e}")
                return event
            except HTTPError as e:  # TODO: specify errors better
                logging.error(f"Communication with ORIS failed!\n{e}")
                return event
            if not event.web:
                event.web = f"https://oris.orientacnisporty.cz/Zavod?id={event.oris_id}"
        elif not event.name or not event.date:
            logging.error(
                f"Each event must have either 'oris_id' or both 'name' and 'date'. "
                f"Event {event_id} has neither."
            )
            return None
        return event

    def get_event(self, season: str, event_id: str) -> Optional[Event]:
        """Get event from loaded events by season and event_id.

        Parameters
        ----------
        season
            Season to which the event belongs (e.g. '21-22')
        event_id : str
            Event identifier in the season (e.g. 'nopb'). It must be unique within
            the season. Config for the event must be stored in
            'data/{season}/events/{event_id}.json' file.

        Returns
        -------
        Optional[Event]
            _description_
        """
        events = self._events.get(season, None)
        if events:
            event = events.get(event_id, None)
            return event
        return None

    @overload
    def get_all_events(self, season: str) -> Optional[Dict[str, Event]]:
        ...

    @overload
    def get_all_events(
        self, season: str, as_dicts: bool = False
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        ...

    def get_all_events(
        self, season: str, as_dicts: bool = False
    ) -> Optional[Union[Dict[str, Event], Dict[str, Dict[str, Any]]]]:
        """Get all events of a season.

        Parameters
        ----------
        season
            season string (e.g. "22-23")
        as_dicts
            return events as dicts (not Event classes)

        Returns
        -------
        Dict
            All events in a season. 'event_id' (NOT oris_id) as keys, events as values.
            Sorted by event date.
        """
        events = self._events.get(season, None)

        if events:
            # Convert classes to dicts
            if as_dicts:
                events = {e_id: e.to_dict() for e_id, e in events.items()}

        return events

    def _assign_bzl_order(self, events: Dict[str, Event]) -> Dict[str, Event]:
        bzl_count = 0
        for event in events.values():
            if event.is_bzl:
                bzl_count += 1
                event.bzl_order = bzl_count
        return events
    
    def get_all_seasons(self) -> List[str]:
        return [f.stem for f in Path("data").glob("*-*")]
