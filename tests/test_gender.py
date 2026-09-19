"""Gender inference, which decides medals in the mixed-gender Z and V categories."""

import pandas as pd
import pytest

from results_calculator.gender import gender_of, is_female


@pytest.mark.parametrize(
    ("reg_no", "name"),
    [
        ("ZBM9051", "Nováková Jana"),  # serial 51 -> female
        ("TBM8888", "Hlavová Hana"),  # serial 88 -> female
        ("ZBM1152", "Beránková Kamila"),
    ],
)
def test_female_registration_numbers(reg_no, name):
    assert is_female(reg_no, name) is True


@pytest.mark.parametrize(
    ("reg_no", "name"),
    [
        ("ZBM9001", "Novák Jan"),  # serial 01 -> male
        ("TBM0101", "Adámek Filip"),
        ("PBM7302", "Trš Lubomír"),
    ],
)
def test_male_registration_numbers(reg_no, name):
    assert is_female(reg_no, name) is False


def test_registration_number_wins_over_the_surname():
    """A man with a female-looking surname is still read from his RegNo."""
    assert is_female("ZBM9001", "Krejčí Jan") is False


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Nováková Jana", True),
        ("Svobodová Eva", True),
        ("Krátká Lucie", True),
        ("Novák Jan", False),
        ("Trš Lubomír", False),
    ],
)
def test_unregistered_runners_fall_back_to_the_surname(name, expected):
    assert is_female("nereg.", name) is expected


@pytest.mark.parametrize(
    ("reg_no", "name"),
    [(None, None), (pd.NA, pd.NA), (float("nan"), ""), ("", ""), ("nereg.", None)],
)
def test_missing_data_never_raises(reg_no, name):
    assert is_female(reg_no, name) in (True, False)


def test_gender_of_returns_the_stored_codes():
    assert gender_of("ZBM9051", "Nováková Jana") == "F"
    assert gender_of("ZBM9001", "Novák Jan") == "M"
