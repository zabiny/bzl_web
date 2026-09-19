"""
Determining a runner's sex, which decides medals in the mixed Z and V categories.

Includes a check against the real published results: H and D *are* the men's
and women's categories (hoši / dívky), so every runner in them is a labelled
example, and the same names and registration-number shapes appear in Z and V.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from results_calculator.sex import (
    _from_registration_number,
    is_female,
    sex_of,
)

# --- registration numbers -------------------------------------------------


@pytest.mark.parametrize(
    ("reg_no", "name"),
    [
        ("ZBM9051", "Nováková Jana"),  # serial 51 -> female
        ("TBM8888", "Hlavová Hana"),
        ("ZBM1152", "Beránková Kamila"),
        ("RBK1553", "Zámečníková Marie"),
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
    assert is_female("ZBM9001", "Krejčí Jan") is False


# --- ORIS temporary ids ---------------------------------------------------


@pytest.mark.parametrize(
    "temporary_id", ["0190001", "0330003", "180001", "30001", "210002", "nereg."]
)
def test_temporary_ids_carry_no_information(temporary_id):
    """
    ORIS gives unregistered runners a plain serial number.

    Reading a digit out of one of these is a coin toss - it was 52% accurate on
    the real data - so they must be rejected and the surname used instead.
    """
    assert _from_registration_number(temporary_id) is None


def test_a_placeholder_club_code_is_still_shaped_like_a_registration_number():
    """
    Known limitation, with one instance in the data.

    "NNN0001" has the shape of a registration number, so its serial is read and
    says male, but it belongs to a woman. Nothing in the string distinguishes a
    placeholder club code from a real one - and in practice her category (D)
    settles it before the number is ever consulted.
    """
    assert _from_registration_number("NNN0001") is False
    assert is_female("NNN0001", "Mašlaňová Ivana", "D") is True


@pytest.mark.parametrize(
    ("temporary_id", "name", "expected"),
    [
        ("0330003", "Stehlíková Alžbeta", True),
        ("0100001", "Sedláčková Alžběta", True),
        ("180001", "Polišenská Lucie", True),
        ("200002", "Jana Slováková", True),  # given name first
        ("0080001", "Hrabec Roman", False),
        ("0260001", "Kinc Martin", False),
    ],
)
def test_temporary_ids_fall_back_to_the_surname(temporary_id, name, expected):
    assert is_female(temporary_id, name) is expected


# --- surnames -------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Nováková Jana", True),
        ("Svobodová Eva", True),
        ("Krátká Lucie", True),
        ("Kozlova Slavka", True),  # entered without diacritics
        ("Malatkova Petra", True),
        ("Polišenská  Kateřina", True),  # doubled space
        ("Novák Jan", False),
        ("Trš Lubomír", False),
    ],
)
def test_unregistered_runners_fall_back_to_the_surname(name, expected):
    assert is_female("nereg.", name) is expected


@pytest.mark.parametrize(
    "name",
    ["Svoboda Jan", "Procházka Petr", "Kučera Tomáš", "Sýkora Adam", "Paseka Tomáš"],
)
def test_common_male_surnames_ending_in_a_are_not_read_as_female(name):
    """A bare "-a" is deliberately not treated as a female ending."""
    assert is_female("nereg.", name) is False


# --- the category settles it where it can ---------------------------------


def test_the_category_overrides_everything_for_h_and_d():
    """H and D are the men's and women's categories, so there is nothing to guess."""
    assert is_female("0190001", "Lepsényi Nóra", "D") is True
    assert is_female("NNN0001", "Mašlaňová Ivana", "D") is True
    assert is_female("ZBM9051", "Nováková Jana", "H") is False


@pytest.mark.parametrize("category", ["Z", "V", "HDD", "ZV", None])
def test_mixed_categories_still_have_to_infer(category):
    assert is_female("ZBM9051", "Nováková Jana", category) is True
    assert is_female("ZBM9001", "Novák Jan", category) is False


# --- robustness -----------------------------------------------------------


@pytest.mark.parametrize(
    ("reg_no", "name"),
    [(None, None), (pd.NA, pd.NA), (float("nan"), ""), ("", ""), ("nereg.", None)],
)
def test_missing_data_never_raises(reg_no, name):
    assert is_female(reg_no, name) in (True, False)


def test_sex_of_returns_the_stored_codes():
    assert sex_of("ZBM9051", "Nováková Jana") == "F"
    assert sex_of("ZBM9001", "Novák Jan") == "M"


# --- accuracy against the real published results --------------------------

#: Measured at 99.66% when this was written. The floor guards against a change
#: that quietly makes the inference worse.
MINIMUM_ACCURACY = 0.99


def _labelled_runners():
    """Every runner in a published H or D table, with their sex known."""
    runners = []
    for path in sorted(Path("data").glob("*/results/overall_[HD].csv")):
        category = re.sub(r"^overall_|\.csv$", "", path.name)
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        for _, row in frame.iterrows():
            runners.append((row["Name"], row["RegNo"], category == "D"))
    return runners


def test_inference_is_accurate_on_the_real_data():
    runners = _labelled_runners()
    if not runners:
        pytest.skip("no published results available")

    # The category is deliberately withheld: this measures the guess that Z and
    # V actually have to rely on.
    correct = sum(1 for name, reg, female in runners if is_female(reg, name) == female)
    accuracy = correct / len(runners)
    assert accuracy >= MINIMUM_ACCURACY, (
        f"sex inference is {accuracy:.2%} accurate over {len(runners)} runners "
        f"({len(runners) - correct} wrong), below the {MINIMUM_ACCURACY:.0%} floor"
    )


def test_inference_is_accurate_for_runners_without_a_registration_number():
    """The case that was broken: ORIS temporary ids and unregistered runners."""
    runners = [
        (name, reg, female)
        for name, reg, female in _labelled_runners()
        if _from_registration_number(reg) is None
    ]
    if not runners:
        pytest.skip("no published results available")

    correct = sum(1 for name, reg, female in runners if is_female(reg, name) == female)
    accuracy = correct / len(runners)
    assert accuracy >= 0.95, (
        f"only {accuracy:.2%} accurate over {len(runners)} runners without a "
        f"registration number"
    )
