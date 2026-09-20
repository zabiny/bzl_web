"""
Locations of the data the site is built from.

Everything lives under a single data directory so it can be mounted into the
container as a volume: publishing a new result is then a file change, not an
image rebuild. Override the location with the ``BZL_DATA_DIR`` environment
variable (tests use this to point at a fixture directory).
"""

import os
from pathlib import Path
from typing import Final

DEFAULT_DATA_DIR: Final = Path("data")


def data_dir() -> Path:
    """Return the root data directory."""
    return Path(os.environ.get("BZL_DATA_DIR", DEFAULT_DATA_DIR))


def season_dir(season: str) -> Path:
    """Return the directory holding one season's data."""
    return data_dir() / season


def events_dir(season: str) -> Path:
    """Return the directory holding one season's event configs."""
    return season_dir(season) / "events"


def results_dir(season: str) -> Path:
    """Return the directory holding one season's results."""
    return season_dir(season) / "results"


#: Matches every per-race results file in a season's results directory.
RACE_RESULTS_GLOB: Final = "points_*.csv"


def overall_results_file(season: str, category: str) -> Path:
    """Return the path of the overall results CSV for one category."""
    return results_dir(season) / f"overall_{category}.csv"


def race_results_file(season: str, oris_id: int) -> Path:
    """Return the path of the per-race results CSV for one race."""
    return results_dir(season) / f"points_{oris_id}.csv"


def merge_decisions_file(season: str) -> Path:
    """Return the path of the recorded duplicate-runner decisions."""
    return results_dir(season) / "merge_decisions.json"
