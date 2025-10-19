import logging
from pathlib import Path
from typing import Any

import pandas as pd
import typer
import unidecode as udc

from results_calculator.cli import app
from results_calculator.race import get_yob

CATEGORIES = ["H", "D", "Z", "V", "HDD"]


@app.command()
def overall(season: str) -> None:
    """Calculate overall results for a given season."""
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
    Go through all 'points_<id>.csv' files and create overall results.

    Processes all race results in a season's directory and creates overall
    results from points for each category.
    """
    # Get filenames and ids of races with assigned points
    filenames, race_ids = _get_filenames_and_ids(season)

    if len(filenames) == 0:
        logging.warning("No event results found for season '%s'!", season)
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
        new_runners = _initialize_new_runners(r_id)

        # Iterate through runners
        for _, race_result in race.iterrows():
            _process_runner(race_result, r_id, ovr_results, new_runners)

        # Add all new runners to overall results of particular category
        ovr_results = _merge_new_runners(ovr_results, new_runners)
    return ovr_results


def _initialize_new_runners(r_id: int) -> dict[str, dict[str, list[Any]]]:
    """Initialize data structure for new runners in a race."""
    new_runners: dict[str, dict[str, list[Any]]] = {}
    for class_desc in CATEGORIES:
        new_runners[class_desc] = {
            "Name": [],
            "RegNo": [],
            f"{r_id}-Place": [],
            f"{r_id}-Points": [],
        }
    return new_runners


def _process_runner(
    race_result: pd.Series,
    r_id: int,
    ovr_results: dict[str, pd.DataFrame],
    new_runners: dict[str, dict[str, list[Any]]],
) -> None:
    """Process a single runner's race result."""
    reg_no = race_result["RegNo"]
    class_desc = race_result["ClassDesc"]

    if class_desc not in ovr_results:
        logging.warning("Category '%s' not found in overall results.", class_desc)
        return

    # Registered runners
    if len(reg_no) == 7 and 64 < ord(reg_no[0]) < 91:
        _process_registered_runner(
            race_result, r_id, reg_no, class_desc, ovr_results, new_runners
        )
    # Not registered runners ('nereg.')
    else:
        _process_unregistered_runner(
            race_result, r_id, class_desc, ovr_results, new_runners
        )


def _process_registered_runner(
    race_result: pd.Series,
    r_id: int,
    reg_no: str,
    class_desc: str,
    ovr_results: dict[str, pd.DataFrame],
    new_runners: dict[str, dict[str, list[Any]]],
) -> None:
    """Process a registered runner's result."""
    if reg_no in ovr_results[class_desc]["RegNo"].values:
        reg_no_mask = ovr_results[class_desc]["RegNo"] == reg_no
        ovr_results[class_desc].loc[reg_no_mask, f"{r_id}-Place"] = race_result["Place"]
        ovr_results[class_desc].loc[reg_no_mask, f"{r_id}-Points"] = race_result[
            "Points"
        ]
    else:
        new_runners[class_desc]["Name"].append(race_result["Name"])
        new_runners[class_desc]["RegNo"].append(reg_no)
        new_runners[class_desc][f"{r_id}-Place"].append(race_result["Place"])
        new_runners[class_desc][f"{r_id}-Points"].append(race_result["Points"])


def _process_unregistered_runner(
    race_result: pd.Series,
    r_id: int,
    class_desc: str,
    ovr_results: dict[str, pd.DataFrame],
    new_runners: dict[str, dict[str, list[Any]]],
) -> None:
    """Process an unregistered runner's result."""
    name = race_result["Name"]

    if name in ovr_results[class_desc]["Name"].values:
        if name in new_runners[class_desc]["Name"]:
            logging.warning(
                "WARNING: Runner without a registration number named "
                "'%s' is already listed in race '%s' in category '%s'.",
                race_result["Name"],
                r_id,
                class_desc,
            )
        else:
            name_mask = ovr_results[class_desc]["Name"] == name
            ovr_results[class_desc].loc[name_mask, f"{r_id}-Place"] = race_result[
                "Place"
            ]
            ovr_results[class_desc].loc[name_mask, f"{r_id}-Points"] = race_result[
                "Points"
            ]
    elif name in new_runners[class_desc]["Name"]:
        logging.warning(
            "WARNING: Runner without a registration number named "
            "'%s' is already listed in race '%s' in category '%s'.",
            race_result["Name"],
            r_id,
            class_desc,
        )
    else:
        new_runners[class_desc]["Name"].append(name)
        new_runners[class_desc]["RegNo"].append(race_result["RegNo"])
        new_runners[class_desc][f"{r_id}-Place"].append(race_result["Place"])
        new_runners[class_desc][f"{r_id}-Points"].append(race_result["Points"])


def _merge_new_runners(
    ovr_results: dict[str, pd.DataFrame],
    new_runners: dict[str, dict[str, list[Any]]],
) -> dict[str, pd.DataFrame]:
    """Merge new runners into overall results."""
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
    filenames = list(season_dir.glob("points_*.csv"))
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

        result = _apply_duplicate_resolution_rules(group)
        dfs.extend(result)

    df = pd.concat(dfs)
    return df


def _apply_duplicate_resolution_rules(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Apply cascade of decision rules to resolve duplicates."""
    # Rule 0: two different results in one race
    if _check_same_race_rule(group):
        return [group.drop(columns=["name_unified"])]

    # Rule 1: One is a RegNo and others are not
    result = _check_regno_rule(group)
    if result is not None:
        ids_2_merge, main_id = result
        return [_merge_runners(group, ids_2_merge, main_id)]

    # Rule 2: One RegNo, different year of birth
    if _check_yob_rule(group):
        return [group.drop(columns=["name_unified"])]

    # Rule 3: One id has more appearances
    result = _check_appearances_rule(group)
    if result is not None:
        ids_2_merge, main_id = result
        return [_merge_runners(group, ids_2_merge, main_id)]

    # Rule 4: manual decision
    return _manual_decision_rule(group)


def _check_same_race_rule(group: pd.DataFrame) -> bool:
    """Check if runners have different results in the same race."""
    for race_col in group.columns[2:]:
        if group[race_col].dropna().nunique() >= 2:
            logging.info(
                "These runners will be kept separated (they both ran in the same "
                "race):\n%s",
                group.T.to_markdown(),
            )
            return True
    return False


def _check_regno_rule(group: pd.DataFrame) -> tuple[pd.Index, int] | None:
    """Check if exactly one runner has a valid RegNo."""
    reg_no_mask = (~group["RegNo"].str.isdigit()) & (
        ~group["RegNo"].str.contains("nereg")
    )
    if reg_no_mask.sum() == 1:
        ids_2_merge = group.index
        main_id = group.index[reg_no_mask].item()
        logging.info(
            "These runners will be merged to one (%s - because it's "
            "the only one with a RegNo)\n%s",
            main_id,
            group.T.to_markdown(),
        )
        return ids_2_merge, main_id
    return None


def _check_yob_rule(group: pd.DataFrame) -> bool:
    """Check if runners have different years of birth."""
    yob = group["RegNo"].apply(get_yob)
    if yob.notna().all() and not yob.eq(yob.iloc[0]).all():
        logging.info(
            "These runners will be kept separated (they have different "
            "year of birth)\n%s",
            group.T.to_markdown(),
        )
        return True
    return False


def _check_appearances_rule(group: pd.DataFrame) -> tuple[pd.Index, int] | None:
    """Check if one runner has more appearances than others."""
    appearances = group.iloc[:, 2:-1].notna().sum(axis=1) // 2
    max_appearances = appearances.max()
    if not appearances.eq(max_appearances).all():
        ids_2_merge = group.index
        # Get the first index value (pandas Index element)
        main_id_value = appearances[appearances == max_appearances].index[0]
        main_id = (
            int(main_id_value)  # type: ignore[arg-type]
            if not isinstance(main_id_value, int)
            else main_id_value
        )
        logging.info(
            "These runners will be merged to one (%s - because it has "
            "the most appearances)\n%s",
            main_id,
            group.T.to_markdown(),
        )
        return ids_2_merge, main_id
    return None


def _manual_decision_rule(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Ask user to manually resolve duplicate runners."""
    typer.echo(70 * "=")
    typer.echo("I'm not able to decide these possible duplicate runners automatically:")
    typer.echo(group.T.to_markdown())
    typer.echo("WHAT TO DO? (choose one of the following options):")
    typer.echo(
        "--> Merge all runners and keep selected Name and RegNo (<id>)\n"
        "--> Keep all runners separated (s)\n"
        "--> Merge selected runners (write comma-separated ids - main first)?"
    )
    decision = input("> ")
    if decision == "s":
        return [group.drop(columns=["name_unified"])]
    if "," in decision:
        ids_2_merge = pd.Index([int(x) for x in decision.split(",")])
        separate_ids = group.index.difference(ids_2_merge)
        main_id = ids_2_merge.to_numpy(dtype=int)[0]
        return [group.loc[separate_ids], _merge_runners(group, ids_2_merge, main_id)]
    ids_2_merge = group.index
    main_id = int(decision)
    return [_merge_runners(group, ids_2_merge, main_id)]


def _merge_runners(
    group: pd.DataFrame, ids_2_merge: pd.Index, main_id: int
) -> pd.DataFrame:
    """Merge multiple runner records into one."""
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
    return pd.DataFrame(merged_runner_data, index=[0])


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
    """Assign overall place to each runner."""
    output_results = {}
    for class_desc in CATEGORIES:
        df = results[class_desc]
        best_n_col = df.filter(regex=r"Best.*").columns[0]

        # Create a helper function to avoid binding loop variable
        def _get_place(points, points_list=df[best_n_col].tolist()):
            return points_list.index(points) + 1

        df["place"] = df[best_n_col].apply(_get_place)
        output_results[class_desc] = df
    return output_results
