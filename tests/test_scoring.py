"""The rules that decide who wins the league."""

from datetime import date

import pandas as pd
import pytest

from results_calculator.overall import count_best_n
from results_calculator.race import (
    _get_points,
    get_yob,
    hdd_max_year,
    zv_kid_year,
    zv_vet_year,
)


@pytest.mark.parametrize(
    ("place", "expected"),
    [
        ("1.", 200),
        ("2.", 190),
        ("3.", 182),
        ("4.", 176),
        ("5.", 172),
        ("6.", 170),  # from here on the curve is 176 - place
        ("7.", 169),
        ("8.", 168),
        ("100.", 76),
        ("175.", 1),
        ("176.", 0),  # beyond the scoring cut-off
        ("300.", 0),
        ("DISK", 0),
        ("MS", 0),
    ],
)
def test_points_for_place(place, expected):
    assert _get_points(place) == expected


def test_points_are_monotonically_decreasing():
    points = [_get_points(f"{p}.") for p in range(1, 176)]
    assert points == sorted(points, reverse=True)
    assert all(p > 0 for p in points)


@pytest.mark.parametrize(
    ("races", "counted"),
    [(0, 0), (1, 1), (2, 2), (3, 2), (4, 3), (5, 3), (6, 4), (7, 4), (8, 5)],
)
def test_count_best_n(races, counted):
    assert count_best_n(races) == counted


def test_count_best_n_is_always_a_majority():
    for races in range(1, 20):
        assert count_best_n(races) > races / 2


@pytest.mark.parametrize(
    ("reg_no", "expected"),
    [
        ("ZBM8501", 1985),
        ("TBM0101", 2001),
        ("PBM7302", 1973),
        ("ZBM9912", 1999),
    ],
)
def test_year_of_birth_from_registration_number(reg_no, expected):
    assert get_yob(reg_no) == expected


@pytest.mark.parametrize("reg_no", ["nereg.", "12345", "", "XX"])
def test_year_of_birth_is_na_when_unknown(reg_no):
    assert pd.isna(get_yob(reg_no))


def test_age_category_years_shift_at_the_summer_rollover():
    before = date(2026, 6, 30)
    after = date(2026, 7, 1)
    assert hdd_max_year(after) == hdd_max_year(before) + 1
    assert zv_kid_year(after) == zv_kid_year(before) + 1
    assert zv_vet_year(after) == zv_vet_year(before) + 1


def test_age_category_years_are_ordered():
    today = date(2026, 1, 15)
    # Veterans are older (smaller year) than youths, who are older than HDD kids.
    assert zv_vet_year(today) < zv_kid_year(today) < hdd_max_year(today)


def test_age_category_years_are_not_frozen_at_import():
    """The web server runs for months; these must be recomputed per call."""
    assert hdd_max_year(date(2025, 1, 1)) != hdd_max_year(date(2026, 1, 1))
