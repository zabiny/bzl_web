import json
import logging  # TODO: setup logger properly
from pathlib import Path
from typing import Dict, Union
from urllib.error import HTTPError

from src.event import Event


class EventManager:
    def create_event_from_config(self, season: str, event_id: str) -> Event:
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
                logging.error(f"Event should have oris is, but hasn't!\n{e}")
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

    def get_all_events(
        self, season: str, as_dicts: bool = False
    ) -> Dict[str, Union[Event, Dict[str, str]]]:
        """Create a dict with all events of a season.

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
        season_dir = Path(f"data/{season}/events/")
        events = {}

        for event_file in season_dir.glob("*.json"):
            event = self.create_event_from_config(season, event_file.stem)
            if event:
                events[event_file.stem] = event

        # Sort by date
        def _event_date(event_tuple):
            # Helper function for sorting by date - class version
            return event_tuple[1].date

        events = dict(sorted(events.items(), key=_event_date))

        # Convert classes to dicts
        if as_dicts:
            events = {e_id: e.to_dict() for e_id, e in events.items()}

        return events
