"""
Determining a runner's sex, which the mixed categories need for medals.

H (hoši) and D (dívky) *are* the men's and women's categories, so for those the
category itself is the answer and nothing has to be inferred. Z (žáci) and V
(veteráni) are mixed, and those are the only places a guess is needed.

Two signals, in order of reliability:

1. The ČSOS registration number, ``ABCYYSS``: three letters for the club, two
   digits for the year of birth, and a two-digit serial that is 50 or above for
   women. This only means anything for a number in exactly that shape - ORIS
   hands unregistered runners a plain numeric id, and reading a digit out of
   one of those is no better than a coin toss.
2. The surname, which in Czech is marked: ``-ová`` or ``-á``.
"""

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

FEMALE = "F"
MALE = "M"

#: A ČSOS registration number: three letters, two digits of birth year, two
#: digits of serial number. Anything else is an ORIS-assigned temporary id and
#: carries no information about sex.
REGISTRATION_NUMBER = re.compile(r"^[A-Za-z]{3}\d{4}$")

#: Index of the first digit of the serial number within ``ABCYYSS``.
SERIAL_FIRST_DIGIT = 5

#: Serial numbers from this value up belong to women.
FEMALE_SERIAL_FROM = 5

#: Czech female surnames end in one of these. "ova" without the diacritic is
#: included because names are sometimes entered unaccented; a bare "a" is not,
#: since plenty of male surnames end in one (Svoboda, Procházka, Kučera).
FEMALE_SURNAME_SUFFIXES = ("ová", "ova", "á")

#: Categories that are single-sex by definition.
CATEGORY_SEX = {"H": MALE, "D": FEMALE}


def _is_missing(value: Any) -> bool:
    """Return whether a value is None or a pandas NA/NaN."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        # pd.isna() of an array-like returns an array, which bool() rejects.
        return False


def _from_registration_number(reg_no: Any) -> bool | None:
    """
    Read sex from a registration number, or None if it is not one.

    Returns True for female. Anything that is not exactly ``ABCYYSS`` - a
    numeric ORIS id, ``nereg.``, a placeholder - returns None so the caller
    falls back to the surname.
    """
    if _is_missing(reg_no):
        return None
    text = str(reg_no).strip()
    if not REGISTRATION_NUMBER.match(text):
        return None
    return int(text[SERIAL_FIRST_DIGIT]) >= FEMALE_SERIAL_FROM


def _from_surname(name: Any) -> bool:
    """
    Guess sex from a Czech name. Returns True for female.

    Every whitespace-separated part is checked rather than just the first,
    because the results sometimes carry the given name first.
    """
    if _is_missing(name):
        return False
    return any(
        part.lower().endswith(FEMALE_SURNAME_SUFFIXES) for part in str(name).split()
    )


def is_female(reg_no: Any, name: Any, category: str | None = None) -> bool:
    """
    Decide whether a runner is female.

    Parameters
    ----------
    reg_no
        Registration number, e.g. ``"ZBM8552"``. Used only when it is a real
        registration number; an ORIS temporary id such as ``"0190001"`` is
        ignored, because its digits say nothing about the runner.
    name
        Runner's name, used as the fallback.
    category
        Race category. ``H`` and ``D`` settle the question outright.

    Returns
    -------
    True if the runner is judged to be female, False when male or
    undetermined. Never raises.

    """
    if category in CATEGORY_SEX:
        return CATEGORY_SEX[category] == FEMALE

    from_reg_no = _from_registration_number(reg_no)
    if from_reg_no is not None:
        return from_reg_no

    return _from_surname(name)


def sex_of(reg_no: Any, name: Any, category: str | None = None) -> str:
    """
    Return ``"F"`` or ``"M"`` for a runner.

    Thin wrapper around :func:`is_female` producing the value stored in the
    ``Sex`` column of the results.
    """
    return FEMALE if is_female(reg_no, name, category) else MALE
