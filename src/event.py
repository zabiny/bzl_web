import logging  # TODO: setup logger properly
from collections import defaultdict
from typing import Dict, Optional
from urllib.error import HTTPError
from datetime import datetime

import requests


class Event:
    def __init__(
        self,
        name: Optional[str] = None,
        date: Optional[str] = None,  # TODO: change to datetime
        difficulty: Optional[str] = None,  # TODO: change to enum, remove optional
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

    def _fetch_oris_data(self, oris_id: int) -> Dict:
        """Get info about an event from ORIS API.

        Retrieve info such as date, GPS coordinates of event center, start time etc.

        Parameters
        ----------
        oris_id
            Event's ORIS ID

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
            oris_json = response.json()["Data"]
        except (ConnectionError, HTTPError, TimeoutError) as e:
            logging.error(f"Communicatoin with ORIS (race {oris_id}) failed!\n{e}")
            oris_json = defaultdict(None)

        result = {
            "name": oris_json["Name"],
            "date": oris_json["Date"],
            "entry_date": oris_json["EntryDate1"],
            "place_desc": oris_json["Place"],
            "gps_lat": oris_json["GPSLat"] if oris_json["GPSLat"] != "0" else None,
            "gps_lon": oris_json["GPSLon"] if oris_json["GPSLon"] != "0" else None,
        }
        return result

    def add_oris_data(self) -> None:
        """Append information about an event retrieved from ORIS API.

        If some info was manually set in config, it's NOT overwritten by ORIS.
        """
        if not self.oris_id:
            raise AttributeError(
                f"Event {self.name} does not have ORIS ID and tries to fetch ORIS data!"
            )
        oris_data = self._fetch_oris_data(self.oris_id)

        for key, oris_value in oris_data.items():
            if getattr(self, key) is None:
                setattr(self, key, oris_value)
