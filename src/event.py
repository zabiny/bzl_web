import json
import logging  # TODO: setup logger properly
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional
from urllib.error import HTTPError

import requests


def get_info_from_oris(oris_id: int) -> Dict:
    """Get info about an event from ORIS API.

    Retrieve info such as date, GPS coordinates of event center, start time etc.
    Only info filled in ORIS is returned.

    Parameters
    ----------
    oris_id
        ORIS ID of an event.

    Returns
    -------
    Dict
        Info about the event in ORIS.
    """
    api_url = (
        "https://oris.orientacnisporty.cz/API/?format=json&method=getEvent&"
        f"id={oris_id}"
    )
    try:
        response = requests.get(api_url)
        print(response.status_code)
        oris_json = response.json()["Data"]
    except (ConnectionError, HTTPError, TimeoutError) as e:
        logging.error(f"Communicatoin with ORIS (race {oris_id}) failed!\n{e}")

    result = {
        "name": oris_json["Name"],
        "date": oris_json["Date"],
        "entry_date": oris_json["EntryDate1"],
        "place_desc": oris_json["Place"],
        "gps_lat": oris_json["GPSLat"],
        "gps_lon": oris_json["GPSLon"],
    }
    return result


def add_oris_info(manual_info: Dict, oris_info: Dict) -> Dict:
    """Append information about an event retrieved from ORIS API.

    Result is an unoin of info items from manual json config and ORIS info.
    If an item is presented in both, the manually specified one is kept.

    Parameters
    ----------
    oris_info
        Event info retrieved from ORIS API
    manual_info
        Event info loaded from json config

    Returns
    -------
    Merged event info.
    """
    result = deepcopy(manual_info)

    for key, oris_value in oris_info.items():
        if key not in result:
            result[key] = oris_value

    return result


class Event:
    def __init__(
        self,
        name: str,
        date: str,  # TODO: change to datetime
        difficulty: Optional[str] = None,  # TODO: change to enum
        bzl_order: Optional[int] = None,
        place_desc: Optional[str] = None,
        description: Optional[str] = None,
        oris_id: Optional[int] = None,
        entry_date: Optional[str] = None,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
        web: Optional[str] = None,
    ) -> None:
        self.name = name
        self.date = date
        self.difficulty = difficulty
        self.bzl_order = bzl_order
        self.place_desc = place_desc
        self.description = description
        self.oris_id = oris_id
        self.entry_date = entry_date
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.web = web

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def create_from_config(cls, season: str, event_id: str):
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

        # Add information from ORIS
        if "oris_id" in config:
            try:
                oris_info = get_info_from_oris(config["oris_id"])
                config = add_oris_info(config, oris_info)
            except HTTPError as e:  # TODO: specify errors better
                logging.error(f"Communication with ORIS failed!\n{e}")
                return None
            if "web" not in config:
                config[
                    "web"
                ] = f"https://oris.orientacnisporty.cz/Zavod?id={config['oris_id']}"

        # Construct the Event instance

        try:
            event = cls(**config)
        except TypeError as e:
            logging.error(f"Event initialization failed!\nConfig: {config}\n{e}")
            return None
        return event
