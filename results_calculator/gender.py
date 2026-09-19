"""
Deriving a runner's gender from their Czech orienteering registration number.

A registration number looks like ``ZBM8501``: three letters for the club, two
digits for the year of birth, and a two-digit serial number that is 50 or above
for women. When a runner has no registration number we fall back to the Czech
surname endings.

This lives next to the rest of the results logic rather than in the web app,
because the categories Z (youth) and V (veterans) are mixed-gender and the
standings have to be able to award medals per gender.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

#: Female Czech surnames essentially always end in one of these.
FEMALE_SURNAME_SUFFIXES = ("ová", "á")

FEMALE = "F"
MALE = "M"


def _is_missing(value: Any) -> bool:
    """Return whether a value is None or a pandas NA/NaN."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        # pd.isna() of an array-like returns an array, which bool() rejects.
        return False


def is_female(reg_no: Any, name: Any) -> bool:
    """
    Infer whether a runner is female.

    Uses the third digit of the registration number (>= 5 means female) and
    falls back to the surname when the registration number is missing or not in
    the standard format.

    Parameters
    ----------
    reg_no
        Registration number, e.g. ``"ZBM8552"``. May be ``"nereg."`` or missing.
    name
        Runner's name in ``"Surname Firstname"`` order, used as the fallback.

    Returns
    -------
    True if the runner is judged to be female, False when male or undetermined.
    Never raises.

    """
    if not _is_missing(reg_no):
        digits = [c for c in str(reg_no).strip() if c.isdigit()]
        if len(digits) >= 3:
            return int(digits[2]) >= 5

    if _is_missing(name):
        return False
    parts = str(name).strip().split()
    if not parts:
        return False
    surname = parts[0]
    return surname.endswith(FEMALE_SURNAME_SUFFIXES)


def gender_of(reg_no: Any, name: Any) -> str:
    """
    Return ``"F"`` or ``"M"`` for a runner.

    Thin wrapper around :func:`is_female` that produces the value stored in the
    ``Gender`` column of the overall results.
    """
    return FEMALE if is_female(reg_no, name) else MALE
