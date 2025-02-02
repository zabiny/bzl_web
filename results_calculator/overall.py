import logging
from pathlib import Path
from typing import Any

import pandas as pd
import unidecode as udc

from results_calculator.cli import app
from results_calculator.race import get_yob

CATEGORIES = ["H", "D", "Z", "V", "HDD"]


@app.command()
def overall(season: str) -> None:
    """
    Calculate overall results for a given season.
    """
    # Get overall results
    ovr_results = _get_overall_results(season)
    if ovr_results is None:
        return

    # Solve duplicities
    ovr_res_wout_dupl = _solve_duplicates(ovr_results)

    # Get best N races
    final_results = _best_n_races(ovr_res_wout_dupl)

    # Assign overall place
    final_results = _assign_overall_place(final_results)

    # Export results
    for class_desc in CATEGORIES:
        final_results[class_desc].to_csv(
            f"data/{season}/results/overall_{class_desc}.csv"
        )


def _get_overall_results(season: str) -> dict[str, pd.DataFrame] | None:
    """
    Goes through all 'points_<id>.csv' files in a season's directory and creates overall
    results from points.
    """
    # Get filenames and ids of races with assigned points
    filenames, race_ids = _get_filenames_and_ids(season)

    if len(filenames) == 0:
        logging.warning(f"No event results found for season '{season}'!")
        return None

    races = {}
    columns_list = ["Name", "RegNo"]

    # For each race add <id>-Place and <id>-Points column
    for r_id, r_filename in zip(race_ids, filenames):
        races[r_id] = pd.read_csv(r_filename, index_col=False)
        columns_list.extend([f"{r_id}-Place", f"{r_id}-Points"])

    # Create overall results - dataframe for every category
    ovr_results = {cat: pd.DataFrame(columns=columns_list) for cat in CATEGORIES}

    # Iterate through races and runners and add them to overall results
    for r_id in race_ids:
        race: pd.DataFrame = races[r_id]
        # Create a data structure for adding new runners
        # (have no evidence in already processed races)
        new_runners: dict[str, dict[str, list[Any]]] = {}
        for class_desc in CATEGORIES:
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
                if class_desc not in ovr_results:
                    logging.warning(
                        f"Category '{class_desc}' not found in overall results."
                    )
                    continue
                if reg_no in ovr_results[class_desc]["RegNo"].values:
                    reg_no_mask = ovr_results[class_desc]["RegNo"] == reg_no
                    ovr_results[class_desc].loc[reg_no_mask, f"{r_id}-Place"] = (
                        race_result["Place"]
                    )
                    ovr_results[class_desc].loc[reg_no_mask, f"{r_id}-Points"] = (
                        race_result["Points"]
                    )
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
                if class_desc not in ovr_results:
                    logging.warning(
                        f"Category '{class_desc}' not found in overall results."
                    )
                    continue
                if name in ovr_results[class_desc]["Name"].values:
                    # Runner with this Name was already added into `new_runners`.
                    # It means two not registered runners with same name in results
                    # of one race in same class.
                    if name in new_runners[class_desc]["Name"]:
                        logging.warning(
                            "WARNING: Runner without a registration number named "
                            f"'{race_result['Name']}' is already listed in race "
                            f"'{r_id}' in category '{class_desc}'."
                        )
                    else:
                        name_mask = ovr_results[class_desc]["Name"] == name
                        ovr_results[class_desc].loc[name_mask, f"{r_id}-Place"] = (
                            race_result["Place"]
                        )
                        ovr_results[class_desc].loc[name_mask, f"{r_id}-Points"] = (
                            race_result["Points"]
                        )
                # Runner with this Name has no results in this category in overall
                # results so far
                else:
                    # Runner with this Name was already added into `new_runners`.
                    # It means two not registered runners with same name in results
                    # of one race in same class.
                    if name in new_runners[class_desc]["Name"]:
                        logging.warning(
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
        for class_desc in CATEGORIES:
            ovr_results[class_desc] = pd.concat(
                [
                    ovr_results[class_desc],
                    pd.DataFrame.from_dict(new_runners[class_desc]),
                ],
                ignore_index=True,
                sort=False,
            )
    return ovr_results


def _get_filenames_and_ids(season: str) -> tuple[list[Path], list[int]]:
    season_dir = Path(f"data/{season}/results")
    filenames = [f for f in season_dir.glob("points_*.csv")]
    race_ids = [int(f.stem[7:]) for f in filenames]
    return filenames, race_ids


def _solve_duplicates(
    input_results: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    output_results = {}

    # Iterate through all categories and try to merge probable duplicates
    for class_desc in CATEGORIES:
        output_results[class_desc] = _solve_duplicates_category(
            input_results[class_desc]
        )
    return output_results


def _solve_duplicates_category(
    class_results: pd.DataFrame,
) -> pd.DataFrame:
    # Unify name (Lowercase names without diacritics matches and trailing spaces)
    class_results["Name"] = class_results["Name"].str.strip()
    class_results["name_unified"] = class_results["Name"].apply(
        lambda x: udc.unidecode(x).lower()
    )
    dfs = []
    for _, group in class_results.groupby("name_unified"):
        # No duplicates, nothing to do
        if len(group) == 1:
            dfs.append(group.drop(columns=["name_unified"]))
            continue

        # Cascade of decision rules
        already_solved = False

        # Rule 0: two different results in one race
        for race_col in group.columns[2:]:
            if group[race_col].dropna().nunique() >= 2:
                dfs.append(group.drop(columns=["name_unified"]))
                logging.info(
                    "These runners will be kept separated (they both ran in the same "
                    "race):\n" + group.T.to_markdown()
                )
                continue

        # Rule 1: One is a RegNo and others are not
        reg_no_mask = (~group["RegNo"].str.isdigit()) & (
            ~group["RegNo"].str.contains("nereg")
        )
        if reg_no_mask.sum() == 1:
            ids_2_merge = group.index
            main_id = group.index[reg_no_mask].item()
            logging.info(
                f"These runners will be merged to one ({main_id} - because it's "
                "the only one with a RegNo)\n" + group.T.to_markdown()
            )
            already_solved = True

        # Rule 2: One RegNo, different year of birth
        if not already_solved:
            yob = group["RegNo"].apply(get_yob)
            if yob.notna().all() and not yob.eq(yob.iloc[0]).all():
                dfs.append(group.drop(columns=["name_unified"]))
                logging.info(
                    "These runners will be kept separated (they have different "
                    "year of birth)\n" + group.T.to_markdown()
                )
                continue

        # Rule 3: One id has more appearances
        if not already_solved:
            appearances = group.iloc[:, 2:-1].notna().sum(axis=1) // 2
            max_appearances = appearances.max()
            if not appearances.eq(max_appearances).all():
                ids_2_merge = group.index
                main_id = appearances[appearances == max_appearances].index[0]
                logging.info(
                    f"These runners will be merged to one ({main_id} - because it has "
                    "the most appearances)\n" + group.T.to_markdown()
                )
                already_solved = True

        # Rule 4: manual decision
        if not already_solved:
            print(70 * "=")
            print(
                "I'm not able to decide these possible duplicate runners automatically:"
            )
            print(group.T.to_markdown())
            print("WHAT TO DO? (choose one of the following options):")
            print(
                "--> Merge all runners and keep selected Name and RegNo (<id>)\n"
                "--> Keep all runners separated (s)\n"
                "--> Merge selected runners (write comma-separated ids - main first)?"
            )
            decision = input("> ")
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

        merged_runner_data = {}
        merged_runner_data["Name"] = group.loc[main_id, "Name"]
        merged_runner_data["RegNo"] = group.loc[main_id, "RegNo"]
        for col in group.columns[2:-1]:  # without Name, RegNo and name_unified
            notna = group.loc[ids_2_merge, col].dropna()
            if notna.empty:
                merged_runner_data[col] = pd.NA
            elif (len(notna) == 1) or ((notna == notna.iloc[0]).all()):
                merged_runner_data[col] = notna.iloc[0]
            else:
                raise ValueError("You are probably merging people that you shouldn't.")
        merged_runner_df = pd.DataFrame(merged_runner_data, index=[0])
        dfs.append(merged_runner_df)
    df = pd.concat(dfs)
    return df


def _best_n_races(results: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    for class_desc in CATEGORIES:
        race_columns = results[class_desc].columns[2:]
        num_of_all_races = len(race_columns) // 2
        num_of_races_to_count = (num_of_all_races // 2) + 1

        total_points = []
        for _, runner in results[class_desc].iterrows():
            points = []
            total_points.append(0)
            for descriptor in race_columns:
                if "Points" in descriptor:
                    if pd.notna(runner[descriptor]):
                        points.append(int(runner[descriptor]))
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


def _assign_overall_place(results: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Assign overall place to each runner.
    """
    output_results = {}
    for class_desc in CATEGORIES:
        df = results[class_desc]
        best_n_col = df.filter(regex=r"Best.*").columns[0]
        df["place"] = df[best_n_col].apply(
            lambda points: df[best_n_col].tolist().index(points) + 1
        )
        output_results[class_desc] = df
    return output_results
