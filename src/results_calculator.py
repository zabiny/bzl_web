from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import unidecode as udc


def get_points(place: str) -> int:
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


def clean_race_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean dataframe for purpose of further processing.

    Replace all empty strings, strings containing only whitespaces and None values
    with NaNs.
    Replace empty places with 'DISK'.
    Replace NaN registrations with 'nereg.'.
    Replace empty UserIDs (ORIS) with NaN.
    """
    df = df.replace(r"^\s*$", np.nan, regex=True).fillna(value=np.nan)
    df["Place"] = df["Place"].fillna(value="DISK")
    df["RegNo"] = df["RegNo"].fillna(value="nereg.")
    df["UserID"] = df["UserID"].fillna(value=np.nan)
    return df


def assign_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign points to runners.

    Iterate through given dataframe and assigns points to every runner based on their
    place in a category.
    """
    df["Points"] = df["Place"].apply(get_points).astype("int32")
    return df


def export_race_to_csv(df: pd.DataFrame, race_id: str):
    """
    Exports race dataframe with assigned points to a .csv file with name in format:
    'points_<race_id>.csv'.
    """
    if "Points" in df.columns:
        df.to_csv(f"points_{race_id}.csv", sep=",", index=False)


def export_class_overall_to_csv(df: pd.DataFrame, class_desc: str):
    """
    Exports overall results dataframe to a .csv file with name in format:
    'overall_<class_desc>.csv'.
    """
    df.to_csv(f"overall_{class_desc}.csv", sep=",")


def race_mode(race_id: str):
    """
    Single race mode.

    Reads race's ORIS id from user's input, loads the race from ORIS,
    assigns points and exports the result into a .csv file.
    """
    # Select race by it's ORIS-id
    try:
        race_id = int(race_id)  # type: ignore
    except ValueError:
        print(f"'{race_id}' can't be converted to an integer.")
        return

    # First, load name and date of selected race. Then load its results.
    url = (
        "https://oris.orientacnisporty.cz/API/"
        f"?format=json&method=getEvent&id={race_id}"
    )
    try:
        response = requests.get(url)
        data = response.json()
        if data["Status"] == "OK":
            name = data["Data"]["Name"]
            date = data["Data"]["Date"]
            print("Event's name:", name)
            print("Event's date:", date)

            # Load results of selected race
            url = (
                f"https://oris.orientacnisporty.cz/API/"
                f"?format=json&method=getEventResults&eventid={race_id}"
            )
            response = requests.get(url)
            data = response.json()
            columns_to_keep = ["ClassDesc", "Place", "Name", "RegNo", "UserID", "Time"]

            # Clean dataset
            try:
                results = clean_race_dataframe(
                    pd.DataFrame.from_dict(data["Data"], orient="index").set_index(
                        "ID"
                    )[columns_to_keep]
                )
            except KeyError as e:
                print(
                    "ERROR: Event DataFrame has a wrong format (result's ID is "
                    "missing). Please check that you used correct ORIS id.\n"
                    f"{e}"
                )
                return

            # Assign points
            results_with_points = assign_points(results)

            # Export to .csv
            export_race_to_csv(results_with_points, race_id)
            print(
                "Event was processed successfully and exported to "
                f"'points_{race_id}.csv'"
            )
        else:
            print(
                "Downloading event data from ORIS failed. (ORIS status: "
                f"{data['Status']})"
            )
    except requests.exceptions.ConnectionError:
        print("Communication with ORIS failed. Check your internet connection please.")


def get_filenames_and_ids(season: str) -> Tuple[List[Path], List[int]]:
    season_dir = Path(f"data/{season}/results")
    filenames = [f for f in season_dir.glob("points_*.csv")]
    race_ids = [int(f.stem[7:]) for f in filenames]
    return filenames, race_ids


def list_races(season: str):
    """
    Lists all races with already assigned points in a season folder.
    With their names and dates.
    """
    filenames, race_ids = get_filenames_and_ids(season)
    for filename, race_id in zip(filenames, race_ids):
        url = (
            "https://oris.orientacnisporty.cz/API/"
            f"?format=json&method=getEvent&id={race_id}"
        )
        try:
            response = requests.get(url)
            data = response.json()
            if data["Status"] == "OK":
                name = data["Data"]["Name"]
                date = data["Data"]["Date"]
                print(f"'{filename}' - '{name}' - {date}")
            else:
                print(
                    "Downloading event data from ORIS failed. (ORIS status: "
                    f"{data['Status']})"
                )
        except requests.exceptions.ConnectionError:
            print(
                "Communication with ORIS failed. Check your internet connection please."
            )


def get_overall_results(season: str) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Goes through all 'points_<id>.csv' files in a season's directory and creates overall
    results from points.
    """
    # Get filenames and ids of races with assigned points
    filenames, race_ids = get_filenames_and_ids(season)

    if len(filenames) == 0:
        print(f"No event results found for season '{season}'!")
        return None

    races = {}
    columns_list = ["Name", "RegNo"]

    # For each race add <id>-Place and <id>-Points column
    for r_id, r_filename in zip(race_ids, filenames):
        races[r_id] = pd.read_csv(r_filename, index_col=False)
        columns_list.extend([f"{r_id}-Place", f"{r_id}-Points"])

    # Create overall results - dataframe for every category
    ovr_results = {
        "H": pd.DataFrame(columns=columns_list),
        "D": pd.DataFrame(columns=columns_list),
        "ZV": pd.DataFrame(columns=columns_list),
        "HDD": pd.DataFrame(columns=columns_list),
    }

    # Iterate through races and runners and add them to overall results
    for r_id in race_ids:
        race: pd.DataFrame = races[r_id]
        # Create a data structure for adding new runners
        # (have no evidence in already processed races)
        new_runners = {}
        for class_desc in ["H", "D", "ZV", "HDD"]:
            new_runners[class_desc] = {
                "Name": [],
                "RegNo": [],
                f"{r_id}-Place": [],
                f"{r_id}-Points": [],
            }
        # Iterate through runners
        for _, race_result in race.iterrows():
            reg_no = race_result["RegNo"]
            class_desc = race_result["ClassDesc"]
            # Registered runners
            if len(reg_no) == 7 and 64 < ord(reg_no[0]) < 91:
                # Runner with this RegNo already has some results in this category in
                # overall results
                if reg_no in ovr_results[class_desc]["RegNo"].values:
                    reg_no_mask = ovr_results[class_desc]["RegNo"] == reg_no
                    ovr_results[class_desc].loc[
                        reg_no_mask, f"{r_id}-Place"
                    ] = race_result["Place"]
                    ovr_results[class_desc].loc[
                        reg_no_mask, f"{r_id}-Points"
                    ] = race_result["Points"]
                # Runner with this RegNo has no results in this category in overall
                # results so far
                else:
                    new_runners[class_desc]["Name"].append(race_result["Name"])
                    new_runners[class_desc]["RegNo"].append(reg_no)
                    new_runners[class_desc][f"{r_id}-Place"].append(
                        race_result["Place"]
                    )
                    new_runners[class_desc][f"{r_id}-Points"].append(
                        race_result["Points"]
                    )
            # Not registered runners ('nereg.')
            else:
                name = race_result["Name"]
                # Runner with this Name already has some results in this category in
                # overall results
                if name in ovr_results[class_desc]["Name"].values:
                    # Runner with this Name was already added into `new_runners`.
                    # It means two not registered runners with same name in results
                    # of one race in same class.
                    if name in new_runners[class_desc]["Name"]:
                        print(
                            "WARNING: Runner without a registration number named "
                            f"'{race_result['Name']}' is already listed in race "
                            f"'{r_id}' in category '{class_desc}'."
                        )
                    else:
                        name_mask = ovr_results[class_desc]["Name"] == name
                        ovr_results[class_desc].loc[
                            name_mask, f"{r_id}-Place"
                        ] = race_result["Place"]
                        ovr_results[class_desc].loc[
                            name_mask, f"{r_id}-Points"
                        ] = race_result["Points"]
                # Runner with this Name has no results in this category in overall
                # results so far
                else:
                    # Runner with this Name was already added into `new_runners`.
                    # It means two not registered runners with same name in results
                    # of one race in same class.
                    if name in new_runners[class_desc]["Name"]:
                        print(
                            "WARNING: Runner without a registration number named "
                            f"'{race_result['Name']}' is already listed in race "
                            f"'{r_id}' in category '{class_desc}'."
                        )
                    else:
                        new_runners[class_desc]["Name"].append(name)
                        new_runners[class_desc]["RegNo"].append(reg_no)
                        new_runners[class_desc][f"{r_id}-Place"].append(
                            race_result["Place"]
                        )
                        new_runners[class_desc][f"{r_id}-Points"].append(
                            race_result["Points"]
                        )
        # Add all new runners to overall results of particular category
        for class_desc in ["H", "D", "ZV", "HDD"]:
            ovr_results[class_desc] = pd.concat(
                [
                    ovr_results[class_desc],
                    pd.DataFrame.from_dict(new_runners[class_desc]),
                ],
                ignore_index=True,
                sort=False,
            )
    return ovr_results


def _solve_duplicates_category(class_results: pd.DataFrame) -> pd.DataFrame:
    # Unify name (Lowercase names without diacritics matches and trailing spaces)
    class_results["Name"] = class_results["Name"].str.strip()
    class_results["name_unified"] = class_results["Name"].apply(
        lambda x: udc.unidecode(x).lower()
    )
    dfs = []
    for _, group in class_results.groupby("name_unified"):
        if len(group) == 1:
            dfs.append(group.drop(columns=["name_unified"]))
            continue

        print(70 * "=")
        print("DUPLICITY")
        print(group.T.to_markdown())

        decision = input(
            "Merge all runners and keep selected Name and RegNo (<id>) / "
            "Keep all runners separated (s) / "
            "Merge selected runners (write comma-separated ids - main first)? > "
        )
        if decision == "s":
            dfs.append(group.drop(columns=["name_unified"]))
            continue
        elif "," in decision:
            ids_2_merge = pd.Index([int(x) for x in decision.split(",")])
            separate_ids = group.index.difference(ids_2_merge)
            main_id = ids_2_merge.to_numpy(dtype=int)[0]
            dfs.append(group[separate_ids])
        else:
            ids_2_merge = group.index
            main_id = int(decision)

        df_tmp = {}
        df_tmp["Name"] = group.loc[main_id, "Name"]
        df_tmp["RegNo"] = group.loc[main_id, "RegNo"]
        for col in group.columns[2:-1]:  # without Name, RegNo and name_unified
            notna = group.loc[ids_2_merge, col].dropna()
            if notna.empty:
                df_tmp[col] = np.nan
            elif (len(notna) == 1) or ((notna == notna.iloc[0]).all()):
                df_tmp[col] = notna.iloc[0]
            else:
                raise ValueError("You are probably merging people that you shouldn't.")
        df_tmp = pd.DataFrame(df_tmp, index=[0])
        print(df_tmp.T.to_markdown())
        dfs.append(df_tmp)
    df = pd.concat(dfs)
    return df


def solve_duplicates(input_results: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    output_results = {}
    # Iterate through all categories and try to merge probable duplicities
    for class_desc in ["H", "D", "ZV", "HDD"]:
        output_results[class_desc] = _solve_duplicates_category(
            input_results[class_desc]
        )

    return output_results


def best_n_races(results: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    for class_desc in ["H", "D", "ZV", "HDD"]:
        num_of_all_races = len(results[class_desc].columns[2:]) // 2
        num_of_races_to_count = (num_of_all_races // 2) + 1
        total_points = []
        columns = results[class_desc].columns[2:]
        for _, runner in results[class_desc].iterrows():
            points = []
            total_points.append(0)
            for descriptor in columns:
                if "Points" in descriptor:
                    if not np.isnan(runner[descriptor]):
                        points.append(int(runner[descriptor]))  # type: ignore
                    else:
                        points.append(0)
            for race_points in sorted(points, reverse=True)[:num_of_races_to_count]:
                total_points[-1] += race_points
        results[class_desc][f"Best{num_of_races_to_count}-Points"] = total_points
        results[class_desc] = (
            results[class_desc]
            .sort_values(f"Best{num_of_races_to_count}-Points", ascending=False)
            .reset_index(drop=True)
        )
    return results


def overall_mode(season: str) -> None:
    ovr_results = get_overall_results(season)
    if ovr_results is None:
        return
    ovr_res_wout_dupl = solve_duplicates(ovr_results)
    final_results = best_n_races(ovr_res_wout_dupl)

    for class_desc in ["H", "D", "ZV", "HDD"]:
        final_results[class_desc].to_csv(
            f"data/{season}/results/overall_{class_desc}.csv"
        )


def print_help():
    """
    Prints help for user interface.
    """
    print("Available commands:")
    print("\thelp\t\t ...\tshow this help")
    print("\trace <oris-id>\t ...\tassign points to a race from ORIS")
    print(
        "\tlist <season>\t ...\tlist races from a season with already assigned points"
    )
    print(
        "\toverall <season> ...\tcalculate intermediate results after already "
        "processed stages in the season"
    )
    print("\tquit\t\t ...\tquit the program")


def resolve_command(command: str):
    """
    Recoqnize what command was used and calls an appropriate function.
    """
    if command == "help":
        print_help()
    elif command[:5] == "race ":
        race_mode(race_id=command[5:])
    elif command[:5] == "list ":
        list_races(season=command[5:])
    elif command[:8] == "overall ":
        overall_mode(season=command[8:])
    elif command == "quit":
        return
    else:
        print(f"Unknown command: '{command}'")


if __name__ == "__main__":
    print("=== BZL - intermediate results calculator ===")
    print_help()
    command = None
    while command != "quit":
        command = input("> ")
        resolve_command(command)
