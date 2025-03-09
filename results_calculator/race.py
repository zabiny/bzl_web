import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import typer
from pandas._libs.missing import NAType

from results_calculator.cli import app

HDD_MAX_YEAR = datetime.now().year - 11 + (datetime.now().month > 6)
ZV_KID_YEAR = datetime.now().year - 15 + (datetime.now().month > 6)
ZV_VET_YEAR = datetime.now().year - 51 + (datetime.now().month > 6)


@app.command()
def race(
    oris_id: int,
    output_dir: Path = typer.Option(
        Path("./"), "--output-dir", "-o", help="Output directory"
    ),
    known_unregs_file: Path = typer.Option(
        Path("./data/known_unregs.json"),
        "--known-unregs",
        "-u",
        help="File with list of known unregistered runners and their year of birth.",
    ),
) -> None:
    """
    Fetch results of a single race from ORIS and save them to a CSV file.

    Parameters
    ----------
    oris_id
        ORIS ID of the race.
    output_dir, optional
        Output directory. If not provided, the current working directory will be used.
    known_unregs_file
        File with list of known unregistered runners and their year of birth.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(known_unregs_file, "r") as f:
            known_unregs = json.load(f)
    except FileNotFoundError:
        logging.warning(
            f"File '{known_unregs_file}' not found! Assuming no unregistered runners."
        )
        known_unregs = []

    # First, get name and date of the race
    url = (
        "https://oris.orientacnisporty.cz/API/"
        f"?format=json&method=getEvent&id={oris_id}"
    )
    try:
        response = requests.get(url)
        race_metadata = response.json()
    except requests.exceptions.ConnectionError:
        logging.error(
            "Communication with ORIS failed. Check your internet connection please."
        )
        return
    except requests.exceptions.HTTPError as e:
        logging.error(f"ORIS returned an error: {e}")
        return

    if race_metadata["Status"] == "OK":
        name = race_metadata["Data"]["Name"]
        date = race_metadata["Data"]["Date"]
        logging.info("Event's name: %s", name)
        logging.info("Event's date: %s", date)

    # Get results
    url = (
        "https://oris.orientacnisporty.cz/API/"
        f"?format=json&method=getEventResults&eventid={oris_id}"
    )
    try:
        response = requests.get(url)
        results_data = response.json()
    except requests.exceptions.ConnectionError:
        logging.error(
            "Communication with ORIS failed. Check your internet connection please."
        )
        return
    except requests.exceptions.HTTPError as e:
        logging.error(f"ORIS returned an error: {e}")
        return

    # Create a dataframe from the results and clean it
    columns_to_keep = ["ClassDesc", "Place", "Name", "RegNo", "UserID", "Time"]
    try:
        df_results = _clean_race_dataframe(
            pd.DataFrame.from_dict(results_data["Data"], orient="index").set_index(
                "ID"
            )[columns_to_keep]
        )
    except KeyError as e:
        logging.error(
            "ERROR: Event DataFrame has a wrong format (result's ID is "
            "missing). Please check that you used correct ORIS id.\n"
            f"{e}"
        )
        return

    # Split ZV class to Z and V
    df_results = _split_zv_class(df_results, known_unregs)

    # Assign points
    df_results["Points"] = df_results["Place"].apply(_get_points)

    # Export to .csv
    output_file = output_dir / f"points_{oris_id}.csv"
    df_results.to_csv(output_file, sep=",", index=False)
    logging.info(f"Event was processed successfully and exported to '{output_file}'")


def _clean_race_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean dataframe for purpose of further processing.

    Replace all empty strings, strings containing only whitespaces and None values
    with pd.NA.
    Replace empty places with 'DISK'.
    Replace NaN registrations with 'nereg.'.
    Replace empty UserIDs (ORIS) with pd.NA.
    """
    df = df.replace(r"^\s*$", pd.NA, regex=True).fillna(value=pd.NA)
    df["Place"] = df["Place"].fillna(value="DISK")
    df["RegNo"] = df["RegNo"].fillna(value="nereg.")
    df["UserID"] = df["UserID"].fillna(value=pd.NA)
    return df


def _split_zv_class(
    df_all: pd.DataFrame, known_unregs: list[dict[str, str | int]]
) -> pd.DataFrame:
    """
    Split ZV class to Z, V and other.
    """
    # Get year of birth from registration number
    df_zv = df_all[df_all["ClassDesc"] == "ZV"].copy()
    df_zv["yob"] = df_zv["RegNo"].apply(get_yob)

    # Try to find unregistered runners in the list of known unregs
    for unreg in known_unregs:
        if (
            unreg["Name"] in df_zv["Name"].values
            and len(df_zv[df_zv["Name"] == unreg["Name"]]) == 1
        ):
            # We know there is only one row with this name (from prev. check).
            # The .all() method is required for proper type checking.
            if df_zv.loc[df_zv["Name"] == unreg["Name"], "yob"].isna().all():
                # Assign all known unreg's attributes to the row (yob, regno, etc.)
                for key in unreg.keys():
                    df_zv.loc[df_zv["Name"] == unreg["Name"], key] = unreg[key]

    # Create Z class (zaci)
    df_z = df_zv[df_zv["yob"].notna() & (df_zv["yob"] >= ZV_KID_YEAR)].reset_index()
    df_z["ClassDesc"] = "Z"

    # Create V class (veterani)
    df_v = df_zv[df_zv["yob"].notna() & (df_zv["yob"] <= ZV_VET_YEAR)].reset_index()
    df_v["ClassDesc"] = "V"

    # Place all other participants in a separate class
    # (without standard registration number or out of age limits)
    df_other = df_zv[
        ~df_zv.index.isin(df_z["ID"]) & ~df_zv.index.isin(df_v["ID"])
    ].reset_index()
    df_other["ClassDesc"] = "ZV-other"

    # Fix places in the splitted classes
    for df in [df_z, df_v]:
        for i in range(len(df)):
            if df.loc[i, "Place"] != "DISK":
                df.loc[i, "Place"] = f"{i + 1}."

    # Drop yob column
    df_z = df_z.drop(columns=["yob"])
    df_v = df_v.drop(columns=["yob"])
    df_other = df_other.drop(columns=["yob"])

    # Set ID as index
    df_z = df_z.set_index("ID")
    df_v = df_v.set_index("ID")
    df_other = df_other.set_index("ID")

    # Concatenate all dataframes
    dfs = [df_all[df_all["ClassDesc"] != "ZV"], df_z, df_v, df_other]
    return pd.concat(dfs)


def get_yob(reg_no: str) -> int | NAType:
    """
    Get year of birth from registration number.
    """
    if reg_no.isdigit() or "nereg" in reg_no:
        return pd.NA
    else:
        try:
            year_str = reg_no[3:5]
            if int(year_str) > datetime.now().year % 100:
                return int("19" + year_str)
            else:
                return int("20" + year_str)
        except ValueError:
            logging.error(
                f"Error parsing year of birth from registration number: {reg_no}"
            )
            return pd.NA


def _get_points(place: str) -> int:
    """
    Transfer given place (str) to points by following rule:
    1st place = 200p
    2nd place = 190p
    3rd place = 182p
    4th place = 176p
    5th place = 172p
    6th place = 170p
    7th place = 169p
    8th place = 168p
    ...
    175th place = 1p
    """
    if place == "1.":
        return 200
    if place == "2.":
        return 190
    if place == "3.":
        return 182
    if place == "4.":
        return 176
    if place == "5.":
        return 172
    if place == "DISK" or place == "MS" or int(place[:-1]) > 175:
        return 0
    else:
        return 176 - int(place[:-1])
