"""The :class:`Event` domain object: one race, from its JSON config plus ORIS."""

import datetime
import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

#: Fields that ORIS can supply. A value set manually in the event's JSON config
#: always wins over the one from ORIS.
ORIS_FIELDS = (
    "name",
    "date",
    "entry_date",
    "place_desc",
    "gps_lat",
    "gps_lon",
    "organizer",
)


class Difficulty(StrEnum):
    """Enumeration of event difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Event:
    """
    Represents an orienteering event.

    An ``Event`` is built from its JSON config and never talks to the network
    itself; ORIS data is handed to it by the
    :class:`~src.event_manager.EventManager` via :meth:`apply_oris_data`.

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

        self.date = datetime.date.fromisoformat(date) if date else None

    @property
    def is_past(self) -> bool | None:
        """
        Whether the event has already happened.

        A property rather than a stored value, so it stays correct in a server
        process that runs for months without a restart.
        """
        if self.date is None:
            return None
        return datetime.date.today() > self.date

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the Event instance to a dictionary for use in templates.

        Returns
        -------
        Dictionary containing all event attributes, including the computed
        ``is_past``.

        """
        return {
            "name": self.name,
            "difficulty": self.difficulty,
            "place_desc": self.place_desc,
            "desc_short": self.desc_short,
            "desc_long": self.desc_long,
            "oris_id": self.oris_id,
            "entry_date": self.entry_date,
            "gps_lat": self.gps_lat,
            "gps_lon": self.gps_lon,
            "web": self.web,
            "images": self.images,
            "video_yt_id": self.video_yt_id,
            "is_bzl": self.is_bzl,
            "organizer": self.organizer,
            "organizer_logo": self.organizer_logo,
            "organizer_logo_large": self.organizer_logo_large,
            "bzl_order": self.bzl_order,
            "date": self.date,
            "is_past": self.is_past,
        }

    def apply_oris_data(self, oris_data: dict[str, Any]) -> None:
        """
        Fill in missing fields from an ORIS payload.

        Anything set manually in the event's JSON config is left untouched.

        Parameters
        ----------
        oris_data
            Normalised data as returned by :meth:`src.oris.OrisClient.get_event`.

        """
        for key in ORIS_FIELDS:
            if getattr(self, key, None) is None and oris_data.get(key) is not None:
                setattr(self, key, oris_data[key])
