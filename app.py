import atexit
import locale
from datetime import date

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, url_for
from werkzeug import Response

from results_calculator.overall import CATEGORIES
from results_calculator.race import HDD_MAX_YEAR, ZV_KID_YEAR, ZV_VET_YEAR
from src.event_manager import EventManager
from src.news import load_news

app = Flask(__name__)
em = EventManager()

# Update the EventManager every 10 mins
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=em.update,
    trigger="interval",
    seconds=600,
    id="event_manager_update",
    name="Update EventManager data",
)
# Enable APScheduler logging
scheduler.print_jobs()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


# Home
@app.route("/")
@app.route("/home")
def home() -> Response:
    """
    Redirect to the news page.

    Returns
    -------
    Redirect response to the news page.

    """
    return redirect(url_for("news"))


# Info
@app.route("/info")
def info() -> str:
    """
    Render the information page.

    Returns
    -------
    Rendered HTML template for the info page.

    """
    return render_template(
        "info.html",
        hdd_max_year=HDD_MAX_YEAR,
        zv_kid_year=ZV_KID_YEAR,
        zv_vet_year=ZV_VET_YEAR,
    )


# News
@app.route("/news")
def news() -> str:
    """
    Render the news page.

    Returns
    -------
    Rendered HTML template for the news page.

    """
    news_items = load_news()
    return render_template("news.html", news=news_items)


# Calendar
@app.route("/<string:season>/calendar")
def calendar(season: str) -> str:
    """
    Render the calendar page for a specific season.

    Parameters
    ----------
    season
        Season identifier (e.g., '24-25').

    Returns
    -------
    Rendered HTML template for the calendar page.

    """
    events = em.get_all_events(season, as_dicts=True)
    return render_template("calendar.html", season=season, events=events)


def _format_results_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Format place and points columns in results dataframe.

    Parameters
    ----------
    df
        DataFrame with place and points columns.

    Returns
    -------
    DataFrame with formatted columns.

    """
    for place_col in df.filter(regex=r".*-Place"):
        if df[place_col].dtype == float:
            df[place_col] = df[place_col].apply(lambda x: f"{x:.0f}.")
    for points_col in df.filter(regex=r".*-Points"):
        if df[points_col].dtype == float:
            df[points_col] = df[points_col].apply(
                lambda x: f"{x:.0f}"
            )  # contains nans -> can't be casted to int
    return df


def _build_oris_name_mapping(events: dict) -> dict:
    """
    Build mapping from ORIS IDs to event names.

    Parameters
    ----------
    events
        Dictionary of event objects.

    Returns
    -------
    Dictionary mapping ORIS IDs to event names.

    """
    oris_id_to_name_mapping = {}
    for ev in events.values():
        if ev.oris_id and ev.name is not None:
            if "BZL" in ev.name:
                name = ev.name.split("BZL: ")[1]
            else:
                name = ev.name
            oris_id_to_name_mapping[ev.oris_id] = name
    return oris_id_to_name_mapping


def _combine_points_and_places(
    df: pd.DataFrame, oris_id_to_name_mapping: dict, oris_ids_in_results: set
) -> tuple[pd.DataFrame, list]:
    """
    Combine points and places columns into single columns per event.

    Parameters
    ----------
    df
        DataFrame with separate points and places columns.
    oris_id_to_name_mapping
        Mapping from ORIS IDs to event names.
    oris_ids_in_results
        Set of ORIS IDs present in results.

    Returns
    -------
    Tuple of modified DataFrame and list of columns to drop.

    """
    cols_to_drop = []
    for oris_id, name in oris_id_to_name_mapping.items():
        if oris_id in oris_ids_in_results:
            df[name] = (
                df[f"{oris_id}-Points"].astype(str)
                + " ("
                + df[f"{oris_id}-Place"].astype(str)
                + ")"
            )
            cols_to_drop.extend([f"{oris_id}-Points", f"{oris_id}-Place"])
    return df, cols_to_drop


# Results
@app.route("/<string:season>/results")
def results(season: str) -> str:
    """
    Render the results page for a specific season.

    Parameters
    ----------
    season
        Season identifier (e.g., '24-25').

    Returns
    -------
    Rendered HTML template for the results page.

    """
    results = {}
    seasons = em.get_all_seasons()
    try:
        # Load results per category
        category_dfs = []
        for category in CATEGORIES:
            df = pd.read_csv(
                f"data/{season}/results/overall_{category}.csv", index_col=0
            )
            df["category"] = category
            df = _format_results_columns(df)
            category_dfs.append(df)
        df = pd.concat(category_dfs)

        # Process DataFrame (rename and drop columns etc.)
        events = em.get_all_events(season)
        if events is None:
            return render_template("results.html", season=season, results={})

        oris_id_to_name_mapping = _build_oris_name_mapping(events)
        oris_ids_in_results = {
            int(x.split("-")[0]) for x in df.columns if x[0].isdigit()
        }

        df, cols_to_drop = _combine_points_and_places(
            df, oris_id_to_name_mapping, oris_ids_in_results
        )

        best_n_col = str(df.filter(regex=r"Best.*").columns[0])
        n = best_n_col.split("-")[0][4:]
        df = (
            df.rename(
                columns={
                    best_n_col: f"Součet ({n} z {len(oris_ids_in_results)})",
                    "Name": "Jméno",
                }
            )
            .replace(["nan (nan.)", "nan (nan)"], "---")
            .drop(columns=cols_to_drop)
        )
        # Split DataFrame per category
        for category in CATEGORIES:
            group_df = df[df["category"] == category].set_index("place", drop=True)
            results[category] = group_df.drop(columns=["category"])
    finally:
        return render_template(
            "results.html", seasons=seasons, season=season, results=results
        )


# Event
@app.route("/<string:season>/event/<string:event_id>/")
def event(season: str, event_id: str) -> str | Response:
    """
    Render the event details page.

    Parameters
    ----------
    season
        Season identifier (e.g., '24-25').
    event_id
        Event identifier.

    Returns
    -------
    Rendered HTML template for the event page, or redirect to home if event not found.

    """
    ev = em.get_event(season, event_id)
    if ev:
        return render_template("event.html", event_data=ev.to_dict())
    return redirect(url_for("home"))


# jinja filters
@app.template_filter("day_from_date")
def _filter_day(input_date: date) -> str:
    if not input_date:
        return ""
    return input_date.strftime("%d")


@app.template_filter("month_and_year_from_date")
def _filter_month_and_year(input_date: date) -> str:
    if not input_date:
        return ""
    locale.setlocale(locale.LC_ALL, "cs_CZ")
    month_and_year = input_date.strftime("%b %Y")
    locale.resetlocale()
    return month_and_year


@app.template_filter("czech_date_from_date")
def _filter_czech_date(input_date: date) -> str:
    if not input_date:
        return ""
    czech_date = input_date.strftime("%d. %m. %Y")
    return czech_date


@app.template_filter("czech_date_from_datetime")
def _filter_date_from_datetime(input_datetime: str) -> str:
    if not input_datetime:
        return ""
    string_date, string_time = input_datetime.split()  # TODO: use time too
    d = date.fromisoformat(string_date)
    czech_date = d.strftime("%d. %m. %Y")
    return czech_date


@app.template_filter("full_season")
def _filter_full_season(season_short: str) -> str:
    year_from, year_to = season_short.split("-")
    return f"20{year_from} - 20{year_to}"


def main() -> None:
    """
    Run the Flask application.

    Notes
    -----
    Starts the application on port 5000 with debug mode enabled.

    """
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
