"""Combines the per-race point tables into the overall season standings."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import typer
import unidecode as udc

from results_calculator.cli import app
from results_calculator.decisions import MERGE, SEPARATE, MergeDecisions
from results_calculator.race import get_yob
from results_calculator.sex import sex_of
from src.paths import merge_decisions_file, overall_results_file, results_dir

CATEGORIES = ["H", "D", "Z", "V", "HDD"]


def count_best_n(num_races: int) -> int:
    """
    Return how many of a season's races count towards the standings.

    A runner's total is the sum of their best ``N`` results out of the
    season's races, where ``N`` is just over half of them: 3 of 5, 4 of 7.
    Exposed so the rules page can state the real numbers instead of a
    hard-coded sentence that silently goes out of date.
    """
    if num_races <= 0:
        return 0
    return (num_races // 2) + 1


@app.command()
def overall(
    season: str,
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=(
            "Never prompt. Ambiguous duplicate runners are kept separate and "
            "reported, so the command can run unattended."
        ),
    ),
) -> None:
    """
    Calculate overall results for a given season.

    Answers to the duplicate-runner questions are recorded in
    ``merge_decisions.json`` next to the results, so re-running the command
    reproduces the same standings instead of asking again.
    """
    # Get overall results
    ovr_results = _get_overall_results(season)
    if ovr_results is None:
        return

    # Solve duplicities, replaying any answers given in previous runs
    decisions = MergeDecisions(merge_decisions_file(season))
    ovr_res_wout_dupl = _solve_duplicates(
        ovr_results, decisions, interactive=not non_interactive
    )
    decisions.save()

    # Get best N races
    final_results = _best_n_races(ovr_res_wout_dupl)

    # Assign overall place
    final_results = _assign_overall_place(final_results)

    # Record sex, so medals in the mixed Z and V categories can be awarded
    # without the website having to re-derive it.
    final_results = _add_sex(final_results)

    # Export results
    for class_desc in CATEGORIES:
        output_file = overall_results_file(season, class_desc)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        final_results[class_desc].to_csv(output_file)


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
    for r_id, r_filename in zip(race_ids, filenames, strict=True):
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
    """
    List a season's race result files, ordered by ORIS id.

    Sorted explicitly: Path.glob() yields whatever order the filesystem happens
    to use, which made the column order of the exported CSVs differ between
    machines for the same input.
    """
    season_dir = results_dir(season)
    filenames = sorted(season_dir.glob("points_*.csv"), key=lambda f: int(f.stem[7:]))
    race_ids = [int(f.stem[7:]) for f in filenames]
    return filenames, race_ids


def _solve_duplicates(
    input_results: dict[str, pd.DataFrame],
    decisions: MergeDecisions,
    interactive: bool = True,
) -> dict[str, pd.DataFrame]:
    output_results = {}

    # Iterate through all categories and try to merge probable duplicates
    for class_desc in CATEGORIES:
        output_results[class_desc] = _solve_duplicates_category(
            input_results[class_desc], decisions, interactive
        )
    return output_results


def _solve_duplicates_category(
    class_results: pd.DataFrame,
    decisions: MergeDecisions,
    interactive: bool = True,
) -> pd.DataFrame:
    # Unify name (Lowercase names without diacritics matches and trailing spaces)
    class_results["Name"] = class_results["Name"].str.strip()
    class_results["name_unified"] = class_results["Name"].apply(
        lambda x: udc.unidecode(x).lower()
    )
    dfs = []
    for name_key, group in class_results.groupby("name_unified"):
        # No duplicates, nothing to do
        if len(group) == 1:
            dfs.append(group.drop(columns=["name_unified"]))
            continue

        result = _apply_duplicate_resolution_rules(
            group, str(name_key), decisions, interactive
        )
        dfs.extend(result)

    df = pd.concat(dfs)
    return df


def _apply_duplicate_resolution_rules(
    group: pd.DataFrame,
    name_key: str,
    decisions: MergeDecisions,
    interactive: bool = True,
) -> list[pd.DataFrame]:
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

    # Rule 4: a previously recorded answer, or ask
    recorded = _apply_recorded_decision(group, name_key, decisions)
    if recorded is not None:
        return recorded
    return _manual_decision_rule(group, name_key, decisions, interactive)


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
            main_id_value if isinstance(main_id_value, int) else int(main_id_value)
        )
        logging.info(
            "These runners will be merged to one (%s - because it has "
            "the most appearances)\n%s",
            main_id,
            group.T.to_markdown(),
        )
        return ids_2_merge, main_id
    return None


def _regno_to_index(group: pd.DataFrame) -> dict[str, Any] | None:
    """
    Map each runner's registration number to their row index.

    Returns None when the numbers are not unique within the group (several
    unregistered runners, say), because then they cannot identify a runner.
    """
    reg_nos = [str(r) for r in group["RegNo"]]
    if len(set(reg_nos)) != len(reg_nos):
        return None
    return dict(zip(reg_nos, group.index, strict=True))


def _apply_recorded_decision(
    group: pd.DataFrame, name_key: str, decisions: MergeDecisions
) -> list[pd.DataFrame] | None:
    """
    Replay a previously recorded answer for this name.

    Returns None when there is no usable recorded decision, in which case the
    caller falls back to asking.
    """
    decision = decisions.get(name_key)
    if decision is None:
        return None

    if decision.get("action") == SEPARATE:
        logging.info("Keeping '%s' separate (recorded decision).", name_key)
        return [group.drop(columns=["name_unified"])]

    if decision.get("action") != MERGE:
        return None

    by_reg_no = _regno_to_index(group)
    if by_reg_no is None:
        logging.warning(
            "Cannot replay the recorded decision for '%s': registration numbers "
            "are not unique within the group.",
            name_key,
        )
        return None

    frames = []
    merged: set[Any] = set()
    for reg_nos in decision.get("groups", []):
        ids = [by_reg_no[r] for r in reg_nos if r in by_reg_no]
        if len(ids) < 2:
            # Someone in the recorded group did not race this season.
            continue
        frames.append(_merge_runners(group, pd.Index(ids), ids[0]))
        merged.update(ids)

    remaining = [i for i in group.index if i not in merged]
    if remaining:
        frames.append(group.loc[remaining].drop(columns=["name_unified"]))

    if not frames:
        return None
    logging.info("Applied recorded merge decision for '%s'.", name_key)
    return frames


def _manual_decision_rule(
    group: pd.DataFrame,
    name_key: str,
    decisions: MergeDecisions,
    interactive: bool = True,
) -> list[pd.DataFrame]:
    """Ask the user to resolve duplicate runners, and remember the answer."""
    if not interactive:
        logging.warning(
            "Cannot decide the possible duplicates named '%s' and running "
            "non-interactively: keeping them separate. Run the command without "
            "--non-interactive once to record a decision.\n%s",
            name_key,
            group.T.to_markdown(),
        )
        return [group.drop(columns=["name_unified"])]

    by_reg_no = _regno_to_index(group)
    index_to_reg_no = (
        {v: k for k, v in by_reg_no.items()} if by_reg_no is not None else None
    )

    typer.echo(70 * "=")
    typer.echo("I'm not able to decide these possible duplicate runners automatically:")
    typer.echo(group.T.to_markdown())
    typer.echo("WHAT TO DO? (choose one of the following options):")
    typer.echo(
        "--> Merge all runners and keep selected Name and RegNo (<id>)\n"
        "--> Keep all runners separated (s)\n"
        "--> Merge selected runners (write comma-separated ids - main first)?"
    )
    valid_ids = set(group.index)

    def parse(answer: str) -> tuple[str, list[Any]] | None:
        """Turn an answer into (kind, ids), or None when it makes no sense."""
        answer = answer.strip()
        if answer == "s":
            return ("separate", [])
        try:
            ids = [int(x) for x in answer.split(",") if x.strip() != ""]
        except ValueError:
            return None
        if not ids or len(set(ids)) != len(ids):
            return None
        if not set(ids).issubset(valid_ids):
            return None
        if "," in answer:
            return ("merge_some", ids)
        return ("merge_all", ids)

    while True:
        raw = input("> ")
        parsed = parse(raw)
        if parsed is not None:
            break
        typer.echo(
            f"Sorry, '{raw.strip()}' is not one of the options. Enter 's', one "
            f"id, or comma-separated ids from {sorted(valid_ids)}."
        )

    kind, chosen_ids = parsed

    def remember(groups: list[list[str]] | None) -> None:
        """Store the answer so the season can be recomputed without asking."""
        if index_to_reg_no is None:
            logging.warning(
                "Not recording the decision for '%s': registration numbers are "
                "not unique within the group.",
                name_key,
            )
            return
        if groups is None:
            decisions.record_separate(name_key)
        else:
            decisions.record_merge(name_key, groups)

    if kind == "separate":
        remember(None)
        return [group.drop(columns=["name_unified"])]

    if kind == "merge_some":
        ids_2_merge = pd.Index(chosen_ids)
        separate_ids = group.index.difference(ids_2_merge)
        if index_to_reg_no is not None:
            remember([[index_to_reg_no[i] for i in chosen_ids]])
        frames = [_merge_runners(group, ids_2_merge, chosen_ids[0])]
        if len(separate_ids):
            frames.append(group.loc[separate_ids].drop(columns=["name_unified"]))
        return frames

    main_id = chosen_ids[0]
    ids_2_merge = group.index
    if index_to_reg_no is not None:
        ordered = [main_id] + [i for i in ids_2_merge if i != main_id]
        remember([[index_to_reg_no[i] for i in ordered]])
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


def _add_sex(results: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add a Sex column right after Name and RegNo."""
    for class_desc in CATEGORIES:
        df = results[class_desc]
        if "Sex" in df.columns:
            continue
        df.insert(
            2,
            "Sex",
            [
                sex_of(reg_no, name, class_desc)
                for reg_no, name in zip(df["RegNo"], df["Name"], strict=True)
            ],
        )
        results[class_desc] = df
    return results


def _best_n_races(results: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    for class_desc in CATEGORIES:
        race_columns = results[class_desc].columns[2:]
        num_of_all_races = len(race_columns) // 2
        num_of_races_to_count = count_best_n(num_of_all_races)

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
