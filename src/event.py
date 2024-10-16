import datetime
import logging  # TODO: setup logger properly
from collections import defaultdict
from typing import Any
from urllib.error import HTTPError

import requests


class Event:
    def __init__(
        self,
        desc_short: str,
        is_bzl: bool,
        difficulty,  # TODO: change to enum, remove optional
        name: str | None = None,
        date: str | None = None,
        place_desc: str | None = None,
        desc_long: str | None = None,
        oris_id: int | None = None,
        entry_date: str | None = None,
        gps_lat: float | None = None,
        gps_lon: float | None = None,
        web: str | None = None,
        logo: str | None = None,
    ) -> None:
        self.name = name
        self.difficulty = difficulty
        self.place_desc = place_desc
        self.desc_short = desc_short
        self.desc_long = desc_long
        self.oris_id = oris_id
        self.entry_date = entry_date
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.web = web
        self.logo = logo
        self.is_bzl = is_bzl

        self.bzl_order: int | None = None  # will be set by event manager

        # Did the event already happened?
        self.date = datetime.date.fromisoformat(date) if date else None
        self.is_past = datetime.date.today() > self.date if self.date else None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__

    def _fetch_oris_data(self, oris_id: int) -> dict[str, Any]:
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
            "date": datetime.date.fromisoformat(oris_json["Date"]),
            "entry_date": oris_json["EntryDate1"],
            "place_desc": oris_json["Place"],
            "gps_lat": oris_json["GPSLat"] if oris_json["GPSLat"] != "0" else None,
            "gps_lon": oris_json["GPSLon"] if oris_json["GPSLon"] != "0" else None,
        }
        result["is_past"] = datetime.date.today() > result["date"]
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
