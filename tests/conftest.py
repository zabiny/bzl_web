"""Shared fixtures: a throwaway data directory and a Flask test client."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Events used by the fixture season. Between them they cover the three shapes
# that matter: full local metadata with GPS, full local metadata without GPS,
# and an event that depends entirely on ORIS.
FIXTURE_EVENTS = {
    "s_mapou": {
        "name": "Závod s mapou",
        "date": "2027-01-10",
        "desc_short": "Závod, který má souřadnice.",
        "desc_long": ["První odstavec.", "Druhý odstavec."],
        "difficulty": "medium",
        "is_bzl": True,
        "gps_lat": "49.2101",
        "gps_lon": "16.5991",
        "place_desc": 'Brno "Žabovřesky"',
    },
    "bez_mapy": {
        "name": "Závod bez mapy",
        "date": "2027-02-14",
        "desc_short": "Závod, který souřadnice nemá.",
        "desc_long": "Jediný odstavec.",
        "difficulty": "hard",
        "is_bzl": True,
    },
    "jen_oris": {
        "oris_id": 99999,
        "desc_short": "Závod, který zná jen ORIS.",
        "difficulty": "easy",
        "is_bzl": False,
    },
}

# Overall standings for the fixture season. H has a plain 1-2-3; V is mixed
# with a tie for the best female place, so medal handling for ties is
# exercised. A registration-number serial of 50 or more means female.
FIXTURE_RESULTS = {
    "H": [
        # Name, RegNo, r1 place, r1 points, r2 place, r2 points, total, place
        ("Novák Jan", "ZBM9001", "1.", 200, "1.", 200, 400, 1),
        ("Dvořák Petr", "ZBM9102", "2.", 190, "2.", 190, 380, 2),
        ("Černý Josef", "ZBM9203", "3.", 182, "3.", 182, 364, 3),
        ("Veselý Karel", "ZBM9304", "4.", 176, "4.", 176, 352, 4),
    ],
    "D": [
        ("Nováková Jana", "ZBM9051", "1.", 200, "1.", 200, 400, 1),
        ("Dvořáková Petra", "ZBM9152", "2.", 190, "2.", 190, 380, 2),
    ],
    "Z": [
        ("Malý Tomáš", "ZBM1501", "1.", 200, "1.", 200, 400, 1),
        ("Malá Tereza", "ZBM1551", "2.", 190, "2.", 190, 380, 2),
    ],
    "V": [
        # Two men take places 1 and 2; two women tie for place 3.
        ("Starý Pavel", "ZBM6001", "1.", 200, "1.", 200, 400, 1),
        ("Starý Milan", "ZBM6102", "2.", 190, "2.", 190, 380, 2),
        ("Stará Marie", "ZBM6051", "3.", 182, "3.", 182, 364, 3),
        ("Stará Eva", "ZBM6252", "3.", 182, "3.", 182, 364, 3),
        ("Stará Alena", "ZBM6353", "5.", 172, "5.", 172, 344, 5),
    ],
    "HDD": [
        ("Malý Ondřej", "ZBM2001", "1.", 200, "1.", 200, 400, 1),
    ],
}

RACE_IDS = (11111, 22222)


def _write_results(results_dir: Path) -> None:
    header = (
        ",Name,RegNo,"
        + ",".join(f"{r}-Place,{r}-Points" for r in RACE_IDS)
        + ",Best1-Points,place"
    )
    for category, rows in FIXTURE_RESULTS.items():
        lines = [header]
        for i, (name, reg, p1, pt1, p2, pt2, total, place) in enumerate(rows):
            lines.append(f"{i},{name},{reg},{p1},{pt1},{p2},{pt2},{total},{place}")
        (results_dir / f"overall_{category}.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


@pytest.fixture(scope="session")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a self-contained data directory for one fictional season."""
    root = tmp_path_factory.mktemp("bzl-data")
    events_dir = root / "26-27" / "events"
    results_dir = root / "26-27" / "results"
    events_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    for event_id, config in FIXTURE_EVENTS.items():
        (events_dir / f"{event_id}.json").write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )
    _write_results(results_dir)
    return root


@pytest.fixture(scope="session")
def flask_app(data_root: Path):
    """Import the Flask app against the fixture data, with no network or scheduler."""
    os.environ["BZL_DATA_DIR"] = str(data_root)
    os.environ["BZL_ORIS_CACHE_DIR"] = str(data_root / ".oris_cache")
    os.environ["BZL_DISABLE_SCHEDULER"] = "1"
    os.environ["MAPY_API_KEY"] = "TEST_MAPY_KEY"

    import app as app_module

    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(flask_app):
    """Return a Flask test client bound to the fixture data."""
    return flask_app.test_client()
