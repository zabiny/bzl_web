"""The Event domain object."""

import datetime

from src.event import Event


def _event(**overrides):
    config = {"desc_short": "Krátký popis", "is_bzl": True, "difficulty": "medium"}
    config.update(overrides)
    return Event(**config)


def test_a_list_description_stays_a_list_of_paragraphs():
    """Joining with a newline used to collapse into one paragraph in HTML."""
    event = _event(desc_long=["První.", "Druhý.", "Třetí."])
    assert event.desc_long == ["První.", "Druhý.", "Třetí."]


def test_a_string_description_is_split_on_newlines():
    event = _event(desc_long="První.\nDruhý.")
    assert event.desc_long == ["První.", "Druhý."]


def test_a_single_line_description_is_one_paragraph():
    assert _event(desc_long="Jen jeden.").desc_long == ["Jen jeden."]


def test_blank_paragraphs_are_dropped():
    assert _event(desc_long=["Text.", "", "   ", "Další."]).desc_long == [
        "Text.",
        "Další.",
    ]


def test_no_description_is_an_empty_list():
    assert _event().desc_long == []


def test_is_past_is_computed_on_every_access():
    """A stored value would go stale in a server that runs for months."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    assert _event(date=yesterday.isoformat()).is_past is True
    assert _event(date=tomorrow.isoformat()).is_past is False


def test_an_event_today_has_not_passed_yet():
    today = datetime.date.today().isoformat()
    assert _event(date=today).is_past is False


def test_is_past_is_none_without_a_date():
    assert _event().is_past is None


def test_to_dict_includes_the_computed_is_past():
    data = _event(date="2020-01-01").to_dict()
    assert data["is_past"] is True
    assert data["desc_short"] == "Krátký popis"


def test_oris_data_fills_in_blanks():
    event = _event(oris_id=1)
    event.apply_oris_data(
        {"name": "Z ORISu", "place_desc": "Brno", "date": datetime.date(2027, 1, 1)}
    )
    assert event.name == "Z ORISu"
    assert event.place_desc == "Brno"


def test_manual_config_always_beats_oris():
    event = _event(name="Ruční název", oris_id=1)
    event.apply_oris_data({"name": "Z ORISu", "place_desc": "Brno"})
    assert event.name == "Ruční název"
    assert event.place_desc == "Brno"


def test_oris_nulls_do_not_overwrite_anything():
    event = _event(place_desc="Brno", oris_id=1)
    event.apply_oris_data({"place_desc": None, "name": None})
    assert event.place_desc == "Brno"


def test_a_race_is_sorted_by_its_real_date():
    event = _event(date="2027-01-10", expected_date="2026-11-28")
    assert event.sort_date == datetime.date(2027, 1, 10)


def test_an_unconfirmed_race_is_sorted_by_its_expected_date():
    """Otherwise it sorts to the end and takes the wrong number in the series."""
    event = _event(expected_date="2026-11-28")
    assert event.sort_date == datetime.date(2026, 11, 28)


def test_a_race_with_neither_date_has_nothing_to_sort_by():
    assert _event().sort_date is None


def test_an_expected_date_never_makes_a_race_past():
    """It is a guess, so it must not claim the race has been run."""
    event = _event(expected_date="2020-01-01")
    assert event.is_past is None
    assert event.date is None
