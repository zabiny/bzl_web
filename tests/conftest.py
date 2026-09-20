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
        "oris_id": 11111,
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
    "bez_data": {
        "name": "Závod bez termínu",
        "desc_short": "Závod, jehož termín zatím neznáme.",
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

# One race's own results, as results_calculator writes them. Between them these
# rows cover everything the per-race statistics have to survive: a tie for the
# best place, a disqualification, a runner out of competition, a category with
# fewer than three finishers, and two classes the league does not score.
#
# ZV-other matters most: its Place values are the placings of the whole ZV
# field, so its "2." is nobody's second place and it must never reach a podium.
FIXTURE_RACE_ROWS = [
    # ClassDesc, Place, Name, RegNo, UserID, Time, Points
    ("H", "1.", "Novák Jan", "ZBM9001", "101", "14:47", 200),
    ("H", "1.", "Dvořák Petr", "ZBM9102", "102", "14:47", 200),
    ("H", "3.", "Černý Josef", "ZBM9203", "103", "15:56", 182),
    ("H", "4.", "Veselý Karel", "ZBM9304", "104", "16:10", 176),
    ("H", "DISK", "Diskvalifikovaný Dan", "ZBM9405", "105", "DISK", 0),
    ("H", "MS", "Mimosoutěžní Milan", "ZBM9506", "106", "15:00", 0),
    ("D", "1.", "Nováková Jana", "ZBM9051", "107", "16:36", 200),
    ("D", "2.", "Dvořáková Petra", "ZBM9152", "108", "18:00", 190),
    ("D", "3.", "Černá Hana", "ZBM9253", "109", "18:30", 182),
    ("Z", "1.", "Malý Tomáš", "ZBM1501", "110", "13:25", 200),
    ("Z", "2.", "Malá Tereza", "ZBM1551", "111", "13:53", 190),
    ("V", "1.", "Starý Pavel", "ZBM6001", "112", "16:32", 200),
    ("V", "2.", "Stará Marie", "ZBM6051", "113", "17:41", 190),
    ("V", "3.", "Starý Milan", "ZBM6102", "114", "18:36", 182),
    # Only two runners: the podium is as long as the category allows.
    ("HDD", "1.", "Malý Ondřej", "ZBM2001", "115", "11:33", 200),
    ("HDD", "2.", "Malá Anna", "ZBM2051", "116", "12:12", 190),
    # Not scored by the league, but they were at the race and are counted.
    ("Expert H", "1.", "Expert Emil", "ZBM7001", "117", "22:00", 0),
    ("ZV-other", "2.", "Mimo Kategorii", "ZBM8001", "118", "19:00", 0),
]

RACE_HEADER_7 = "ClassDesc,Place,Name,RegNo,UserID,Time,Points"
#: Files written since the Sex column was added carry an eighth column.
RACE_HEADER_8 = RACE_HEADER_7 + ",Sex"

# Deliberately not the real names, so a test asserting on them proves the page
# is reading the configuration rather than a string baked into a template.
FIXTURE_SITE = {
    "title": "Testovací zimní liga",
    "short_title": "TZL",
    "description": "Popis testovací ligy.",
    "url": "https://example.test",
    "contact_email": "test@example.test",
    "og_image": "og-image.png",
    "organizer": {
        "name": "Testovací oddíl",
        "url": "https://oddil.example.test",
        "logo": "logos/zbm_large.png",
    },
    "partners": [
        {
            "name": "Testpartner",
            "url": "https://partner.example.test",
            "logo": "logos/mbm.png",
        }
    ],
}


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


def _write_race_results(results_dir: Path) -> None:
    """
    Write the per-race results files.

    Race 11111 belongs to the ``s_mapou`` event and gets the seven-column
    header the committed files use. Race 22222 has no event of its own, so it
    doubles as the orphan-results case, and is written with the eight-column
    header so that both shapes are exercised.
    """
    rows = [",".join(str(cell) for cell in row) for row in FIXTURE_RACE_ROWS]
    (results_dir / "points_11111.csv").write_text(
        "\n".join([RACE_HEADER_7, *rows]) + "\n", encoding="utf-8"
    )
    with_sex = [
        ",".join(str(cell) for cell in row) + ("," + ("F" if "ová" in row[2] else "M"))
        for row in FIXTURE_RACE_ROWS
    ]
    (results_dir / "points_22222.csv").write_text(
        "\n".join([RACE_HEADER_8, *with_sex]) + "\n", encoding="utf-8"
    )


@pytest.fixture(scope="session")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a self-contained data directory for one fictional season."""
    root = tmp_path_factory.mktemp("bzl-data")
    events_dir = root / "26-27" / "events"
    results_dir = root / "26-27" / "results"
    events_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    (root / "site.json").write_text(
        json.dumps(FIXTURE_SITE, ensure_ascii=False), encoding="utf-8"
    )
    for event_id, config in FIXTURE_EVENTS.items():
        (events_dir / f"{event_id}.json").write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )
    _write_results(results_dir)
    _write_race_results(results_dir)
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
