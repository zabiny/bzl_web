"""Building the results tables, above all the medal rules."""

import pytest

from src.event_manager import EventManager
from src.oris import OrisClient
from src.results import _competition_ranks, load_season_results


@pytest.fixture
def season(data_root, monkeypatch):
    monkeypatch.setenv("BZL_DATA_DIR", str(data_root))
    manager = EventManager(oris_client=OrisClient(cache_dir=data_root / ".cache"))
    return load_season_results("26-27", manager.get_all_events("26-27") or {})


def test_missing_season_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("BZL_DATA_DIR", str(tmp_path))
    assert load_season_results("99-99", {}) is None


def test_every_category_is_present(season):
    assert set(season.tables) == {"H", "D", "Z", "V", "HDD"}


def test_internal_columns_are_not_rendered(season):
    for table in season.tables.values():
        assert "category" not in table.columns
        assert "Sex" not in table.columns


def test_registration_numbers_stay_visible(season):
    assert "RegNo" in season.tables["H"].columns


def test_the_total_column_states_the_rule(season):
    assert any(col.startswith("Součet (") for col in season.tables["H"].columns)


def test_top_three_get_medals(season):
    medals = season.medals["H"]
    assert medals[(1, "Novák Jan")] == "medal-gold"
    assert medals[(2, "Dvořák Petr")] == "medal-silver"
    assert medals[(3, "Černý Josef")] == "medal-bronze"
    assert (4, "Veselý Karel") not in medals


def test_mixed_categories_award_medals_per_sex(season):
    """In V the leading man and the leading woman both get gold."""
    medals = season.medals["V"]
    assert medals[(1, "Starý Pavel")] == "medal-gold"
    assert medals[(2, "Starý Milan")] == "medal-silver"
    # The women are ranked within their own group, not by the overall place.
    assert medals[(3, "Stará Marie")] == "medal-gold"
    assert medals[(3, "Stará Eva")] == "medal-gold"


def test_a_tie_gives_both_runners_the_same_medal(season):
    """Two women tie for third overall; both are first among the women."""
    medals = season.medals["V"]
    assert medals[(3, "Stará Marie")] == medals[(3, "Stará Eva")] == "medal-gold"
    # After two golds the next woman takes bronze, not silver.
    assert medals[(5, "Stará Alena")] == "medal-bronze"


@pytest.mark.parametrize(
    ("places", "expected"),
    [
        ([1, 2, 3], [1, 2, 3]),
        ([1, 1, 3], [1, 1, 3]),  # standard competition ranking
        ([1, 1, 1, 4], [1, 1, 1, 4]),
        ([3, 3, 5], [1, 1, 3]),  # re-ranked inside a sex group
        ([2, 4, 4, 7], [1, 2, 2, 4]),
    ],
)
def test_competition_ranking(places, expected):
    assert _competition_ranks(places) == expected


def test_races_a_runner_missed_show_a_dash(season):
    table = season.tables["H"]
    assert not table.astype(str).apply(lambda c: c.str.contains("nan")).to_numpy().any()
