import datetime
import logging  # TODO: setup logger properly
from collections import defaultdict
from enum import StrEnum
from typing import Any
from urllib.error import HTTPError

import requests


class Difficulty(StrEnum):
    """Enumeration of event difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Event:
    """
    Represents an orienteering event.

    Attributes
    ----------
    name
        Event name.
    difficulty
        Event difficulty level.
    place_desc
        Description of the event location.
    desc_short
        Short description of the event.
    desc_long
        Long description of the event.
    oris_id
        ORIS database ID.
    entry_date
        Entry deadline date.
    gps_lat
        GPS latitude of event center.
    gps_lon
        GPS longitude of event center.
    web
        Event website URL.
    images
        List of image URLs.
    video_yt_id
        YouTube video ID.
    is_bzl
        Whether this is an event of the BZL series.
    organizer
        Organizer name.
    organizer_logo
        URL to organizer logo.
    organizer_logo_large
        URL to large organizer logo.
    bzl_order
        Order in BZL series.
    date
        Event date.
    is_past
        Whether the event has already occurred.

    """

    def __init__(
        self,
        desc_short: str,
        is_bzl: bool,
        difficulty: Difficulty,
        name: str | None = None,
        date: str | None = None,
        place_desc: str | None = None,
        desc_long: str | list[str] | None = None,
        oris_id: int | None = None,
        entry_date: str | None = None,
        gps_lat: float | None = None,
        gps_lon: float | None = None,
        web: str | None = None,
        organizer: str | None = None,
        organizer_logo: str | None = None,
        organizer_logo_large: str | None = None,
        images: list[str] | None = None,
        video_yt_id: str | None = None,
    ) -> None:
        """
        Initialize an Event instance.

        Parameters
        ----------
        desc_short
            Short description of the event.
        is_bzl
            Whether this is an event of the BZL series.
        difficulty
            Event difficulty level.
        name
            Event name (can be fetched from ORIS if not provided).
        date
            Event date in ISO format (YYYY-MM-DD).
        place_desc
            Description of the event location.
        desc_long
            Long description of the event (string or list of strings).
        oris_id
            ORIS database ID for fetching additional data.
        entry_date
            Entry deadline date.
        gps_lat
            GPS latitude of event center.
        gps_lon
            GPS longitude of event center.
        web
            Event website URL.
        organizer
            Organizer name.
        organizer_logo
            URL to organizer logo.
        organizer_logo_large
            URL to large organizer logo.
        images
            List of image URLs.
        video_yt_id
            YouTube video ID.

        """
        self.name = name
        self.difficulty = difficulty
        self.place_desc = place_desc
        self.desc_short = desc_short
        self.desc_long = (
            "\n".join(desc_long) if isinstance(desc_long, list) else desc_long
        )
        self.oris_id = oris_id
        self.entry_date = entry_date
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.web = web
        self.images = images
        self.video_yt_id = video_yt_id
        self.is_bzl = is_bzl
        self.organizer = organizer
        self.organizer_logo = organizer_logo
        self.organizer_logo_large = organizer_logo_large
        self.bzl_order: int | None = None  # will be set by event manager

        # Did the event already happened?
        self.date = datetime.date.fromisoformat(date) if date else None
        self.is_past = datetime.date.today() > self.date if self.date else None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the Event instance to a dictionary.

        Returns
        -------
        Dictionary containing all event attributes.

        """
        return self.__dict__

    def _fetch_oris_data(self, oris_id: int) -> dict[str, Any]:
        """
        Get info about an event from ORIS API.

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
            logging.error("Communication with ORIS (race %s) failed!\n%s", oris_id, e)
            oris_json = defaultdict(None)

        result = {
            "name": oris_json["Name"],
            "date": datetime.date.fromisoformat(oris_json["Date"]),
            "entry_date": oris_json["EntryDate1"],
            "place_desc": oris_json["Place"],
            "gps_lat": oris_json["GPSLat"] if oris_json["GPSLat"] != "0" else None,
            "gps_lon": oris_json["GPSLon"] if oris_json["GPSLon"] != "0" else None,
            "organizer": oris_json["Org1"]["Name"],
        }
        result["is_past"] = datetime.date.today() > result["date"]
        return result

    def add_oris_data(self) -> None:
        """
        Append information about an event retrieved from ORIS API.

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
