"""
Turns the overall results CSVs into the tables shown on the results page.

Kept out of ``app.py`` so the view function stays a view function, and so the
table building can be tested without a request context.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from results_calculator.gender import FEMALE, gender_of
from results_calculator.overall import CATEGORIES
from src.paths import overall_results_file

logger = logging.getLogger(__name__)

#: Shown instead of a score for a race the runner did not start.
MISSING_CELL = "---"

#: Categories that are mixed-gender, and therefore get medals per gender.
MIXED_GENDER_CATEGORIES = ("Z", "V")

#: CSS classes for the first three places, in order.
MEDAL_CLASSES = ("medal-gold", "medal-silver", "medal-bronze")

#: Columns used for bookkeeping that must not be rendered as table cells.
INTERNAL_COLUMNS = ("category", "Gender")


@dataclass
class SeasonResults:
    """
    The rendered-ready standings of one season.

    Attributes
    ----------
    tables
        One DataFrame per category, indexed by finishing place.
    medals
        ``category -> {(place, name): css_class}`` for the first three places.
        Keyed by name as well as place so that tied places work.
    counted_races
        How many races count towards the total.
    total_races
        How many races the season has results for.

    """

    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    medals: dict[str, dict[tuple[int, str], str]] = field(default_factory=dict)
    counted_races: int = 0
    total_races: int = 0


def load_season_results(season: str, events: dict[str, Any]) -> SeasonResults | None:
    """
    Build the results tables for one season.

    Parameters
    ----------
    season
        Season identifier (e.g. ``"25-26"``).
    events
        The season's events, as returned by
        :meth:`~src.event_manager.EventManager.get_all_events`. Used to label
        each race column with the event's name instead of its ORIS id.

    Returns
    -------
    The season's results, or ``None`` if the season simply has no results yet.

    Raises
    ------
    Exception
        Anything other than a missing file is a real problem and is allowed to
        propagate, rather than being turned into a silently empty page.

    """
    try:
        df = _read_all_categories(season)
    except FileNotFoundError:
        logger.info("No results files for season %s yet.", season)
        return None

    race_names = _oris_id_to_name(events)
    race_ids = _race_ids_in(df)

    df, per_race_columns = _combine_points_and_places(df, race_names, race_ids)

    total_col = str(df.filter(regex=r"^Best.*").columns[0])
    counted_races = int(total_col.split("-", 1)[0].removeprefix("Best"))

    df = df.rename(
        columns={
            total_col: f"Součet ({counted_races} z {len(race_ids)})",
            "Name": "Jméno",
        }
    ).drop(columns=per_race_columns)

    medals = _medals_by_category(df)

    tables = {}
    for category in CATEGORIES:
        table = df[df["category"] == category].set_index("place", drop=True)
        tables[category] = table.drop(
            columns=[c for c in INTERNAL_COLUMNS if c in table.columns]
        )

    return SeasonResults(
        tables=tables,
        medals=medals,
        counted_races=counted_races,
        total_races=len(race_ids),
    )


def _read_all_categories(season: str) -> pd.DataFrame:
    """Read every category's CSV and stack them into one frame."""
    frames = []
    for category in CATEGORIES:
        frame = pd.read_csv(overall_results_file(season, category), index_col=0)
        frame["category"] = category
        if "Gender" not in frame.columns:
            # Older CSVs predate the Gender column; derive it on the fly so the
            # page still works before the files are regenerated.
            reg_nos = frame["RegNo"] if "RegNo" in frame else [None] * len(frame)
            names = frame["Name"] if "Name" in frame else [None] * len(frame)
            frame["Gender"] = [
                gender_of(reg_no, name)
                for reg_no, name in zip(reg_nos, names, strict=True)
            ]
        frames.append(frame)
    return pd.concat(frames)


def _oris_id_to_name(events: dict[str, Any]) -> dict[int, str]:
    """
    Map ORIS ids to the event names used as column headers.

    The ``"BZL: "`` prefix ORIS carries is stripped so the column stays narrow.
    """
    mapping = {}
    for event in events.values():
        oris_id = event.oris_id if hasattr(event, "oris_id") else event.get("oris_id")
        name = event.name if hasattr(event, "name") else event.get("name")
        if oris_id and name:
            mapping[oris_id] = name.split("BZL: ", 1)[-1]
    return mapping


def _race_ids_in(df: pd.DataFrame) -> set[int]:
    """Return the ORIS ids that actually have columns in the results."""
    return {int(c.split("-")[0]) for c in df.columns if c[0].isdigit()}


def _format_place(value: Any) -> str:
    """Render a place cell: ``3.0`` -> ``"3."``, ``"DISK"`` stays as it is."""
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.0f}."
    return str(value)


def _format_points(value: Any) -> str:
    """Render a points cell as a whole number."""
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.0f}"
    return str(value)


def _combine_points_and_places(
    df: pd.DataFrame, race_names: dict[int, str], race_ids: set[int]
) -> tuple[pd.DataFrame, list[str]]:
    """
    Fold each race's points and place columns into one ``"190 (2.)"`` column.

    Returns the frame plus the list of now-redundant source columns to drop.
    """
    consumed = []
    for oris_id, name in race_names.items():
        if oris_id not in race_ids:
            continue
        points = df[f"{oris_id}-Points"]
        places = df[f"{oris_id}-Place"]
        combined = points.map(_format_points) + " (" + places.map(_format_place) + ")"
        # A runner who missed the race gets a dash rather than "nan (nan)".
        df[name] = combined.mask(points.isna() & places.isna(), MISSING_CELL)
        consumed.extend([f"{oris_id}-Points", f"{oris_id}-Place"])
    return df, consumed


def _competition_ranks(places: list[int]) -> list[int]:
    """
    Rank a group using standard competition ranking (1, 2, 2, 4).

    Both runners tied for the best place come out as rank 1, so both get gold.
    """
    return [sum(1 for other in places if other < place) + 1 for place in places]


def _medals_by_category(df: pd.DataFrame) -> dict[str, dict[tuple[int, str], str]]:
    """
    Work out which rows get a gold, silver or bronze highlight.

    In H, D and HDD the first three places are medalled directly. Z and V are
    mixed-gender categories, so the top three of each gender are medalled and
    the ranking is recomputed within the gender group.
    """
    medals: dict[str, dict[tuple[int, str], str]] = {}

    for category in CATEGORIES:
        category_rows = df[df["category"] == category]
        medal_map: dict[tuple[int, str], str] = {}

        if category in MIXED_GENDER_CATEGORIES:
            groups = [
                category_rows[category_rows["Gender"] == FEMALE],
                category_rows[category_rows["Gender"] != FEMALE],
            ]
        else:
            groups = [category_rows]

        for group in groups:
            if group.empty:
                continue
            places = [int(p) for p in group["place"]]
            names = [str(n) for n in group["Jméno"]]
            for place, name, rank in zip(
                places, names, _competition_ranks(places), strict=True
            ):
                if rank <= len(MEDAL_CLASSES):
                    medal_map[(place, name)] = MEDAL_CLASSES[rank - 1]

        medals[category] = medal_map

    return medals
