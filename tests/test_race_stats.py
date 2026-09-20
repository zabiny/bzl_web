"""Per-race statistics: participant counts and podiums for the calendar."""

import pytest

from src.race_stats import load_race_stats, race_stats_by_event
from tests.conftest import FIXTURE_EVENTS, FIXTURE_RACE_ROWS

SEASON = "26-27"


@pytest.fixture
def stats(data_root, monkeypatch):
    """Statistics for the fixture season, read from the fixture data."""
    monkeypatch.setenv("BZL_DATA_DIR", str(data_root))
    return load_race_stats(SEASON)


def test_participants_count_everyone_who_started(stats):
    """Including DISK, out-of-competition, and classes the league does not score."""
    assert stats[11111].participants == len(FIXTURE_RACE_ROWS)


def test_podium_holds_only_the_league_categories_in_order(stats):
    """`Expert H` and `ZV-other` are at the race but never on a podium."""
    assert list(stats[11111].podium) == ["H", "D", "Z", "V", "HDD"]


def test_a_tie_for_first_puts_two_runners_on_the_top_step(stats):
    """The Place column is already competition-ranked: 1., 1., 3."""
    places = [entry.place for entry in stats[11111].podium["H"]]
    assert places == [1, 1, 3]

    names = {entry.name for entry in stats[11111].podium["H"]}
    assert names == {"Novák Jan", "Dvořák Petr", "Černý Josef"}


def test_disqualified_and_out_of_competition_runners_are_not_placed(stats):
    """Neither scored points, so neither belongs on the podium."""
    placed = {
        entry.name for entries in stats[11111].podium.values() for entry in entries
    }
    assert "Diskvalifikovaný Dan" not in placed
    assert "Mimosoutěžní Milan" not in placed


def test_a_category_with_two_runners_gets_a_podium_of_two(stats):
    assert len(stats[11111].podium["HDD"]) == 2


def test_podium_entries_carry_the_time(stats):
    assert stats[11111].podium["D"][0].time == "16:36"


def test_the_eight_column_file_parses_like_the_seven_column_one(stats):
    """Files written since the Sex column was added must read identically."""
    assert stats[22222].participants == stats[11111].participants
    assert stats[22222].podium == stats[11111].podium


def test_events_without_results_simply_have_no_statistics(data_root, monkeypatch):
    monkeypatch.setenv("BZL_DATA_DIR", str(data_root))
    by_event = race_stats_by_event(SEASON, FIXTURE_EVENTS)

    # s_mapou is oris_id 11111, which has a results file.
    assert "s_mapou" in by_event
    # bez_mapy has no ORIS id at all; jen_oris has one, but no results file.
    assert "bez_mapy" not in by_event
    assert "jen_oris" not in by_event


def test_results_with_no_event_never_reach_the_calendar(data_root, monkeypatch):
    """Race 22222 has results but no event config, so nothing can show it."""
    monkeypatch.setenv("BZL_DATA_DIR", str(data_root))
    assert 22222 in load_race_stats(SEASON)
    assert 22222 not in {
        s.oris_id for s in race_stats_by_event(SEASON, FIXTURE_EVENTS).values()
    }


def test_a_broken_results_file_is_skipped_and_the_others_still_load(
    tmp_path, monkeypatch
):
    """A results page may be wrong; the calendar must still render."""
    results = tmp_path / "26-27" / "results"
    results.mkdir(parents=True)
    header = "ClassDesc,Place,Name,RegNo,UserID,Time,Points\n"
    (results / "points_11111.csv").write_text(
        header + "H,1.,Novák Jan,ZBM9001,1,14:47,200\n", encoding="utf-8"
    )
    (results / "points_33333.csv").write_text(
        "not,a,results,file\n1,2\n", encoding="utf-8"
    )
    (results / "points_notanumber.csv").write_text("whatever\n", encoding="utf-8")
    monkeypatch.setenv("BZL_DATA_DIR", str(tmp_path))

    stats = load_race_stats(SEASON)

    assert 11111 in stats
    assert 33333 not in stats


def test_a_new_results_file_is_picked_up_without_a_restart(tmp_path, monkeypatch):
    """`data/` is a mounted volume: publishing results is a file edit."""
    results = tmp_path / "26-27" / "results"
    results.mkdir(parents=True)
    path = results / "points_11111.csv"
    header = "ClassDesc,Place,Name,RegNo,UserID,Time,Points\n"
    path.write_text(header + "H,1.,Novák Jan,ZBM9001,1,14:47,200\n", encoding="utf-8")
    monkeypatch.setenv("BZL_DATA_DIR", str(tmp_path))

    assert load_race_stats(SEASON)[11111].participants == 1

    path.write_text(
        header
        + "H,1.,Novák Jan,ZBM9001,1,14:47,200\n"
        + "H,2.,Dvořák Petr,ZBM9102,2,15:00,190\n",
        encoding="utf-8",
    )

    assert load_race_stats(SEASON)[11111].participants == 2


def test_a_season_with_no_results_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("BZL_DATA_DIR", str(tmp_path))
    assert load_race_stats("99-00") == {}
