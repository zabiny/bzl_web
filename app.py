import atexit
import locale
from datetime import date

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, url_for
from werkzeug import Response

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
    return redirect(url_for("news"))


# Info
@app.route("/info")
def info() -> str:
    hdd_max_year = date.today().year - 10 + (date.today().month > 6)
    zv_kid_year = date.today().year - 14 + (date.today().month > 6)
    zv_vet_year = date.today().year - 45 + (date.today().month > 6)
    return render_template(
        "info.html",
        hdd_max_year=hdd_max_year,
        zv_kid_year=zv_kid_year,
        zv_vet_year=zv_vet_year,
    )


# News
@app.route("/news")
def news() -> str:
    news_items = load_news()
    return render_template("news.html", news=news_items)


# Calendar
@app.route("/<string:season>/calendar")
def calendar(season: str) -> str:
    events = em.get_all_events(season, as_dicts=True)
    return render_template("calendar.html", season=season, events=events)


# Results
@app.route("/<string:season>/results")
def results(season: str) -> str:
    results = {}
    seasons = em.get_all_seasons()
    try:
        # Load results per category
        category_dfs = []
        for category in ["H", "D", "ZV", "HDD"]:
            df = pd.read_csv(
                f"data/{season}/results/overall_{category}.csv", index_col=0
            )
            df["category"] = category
            # Assign overall place
            best_n_col = df.filter(regex=r"Best.*").columns[0]
            df["place"] = df[best_n_col].apply(
                lambda points: df[best_n_col].tolist().index(points) + 1
            )
            # Fix formatting
            for place_col in df.filter(regex=r".*-Place"):
                if df[place_col].dtype == float:
                    df[place_col] = df[place_col].apply(lambda x: f"{x:.0f}.")
            for points_col in df.filter(regex=r".*-Points"):
                if df[points_col].dtype == float:
                    df[points_col] = df[points_col].apply(
                        lambda x: f"{x:.0f}"
                    )  # contains nans -> can't be casted to int
            category_dfs.append(df)
        df = pd.concat(category_dfs)

        # Process DataFrame (rename and drop columns etc.)
        events = em.get_all_events(season)
        if events is None:
            return render_template("results.html", season=season, results={})
        oris_id_to_name_mapping = {
            ev.oris_id: ev.name for ev in events.values() if ev.oris_id
        }

        oris_ids_in_results = set(
            [int(x.split("-")[0]) for x in df.columns if x[0].isdigit()]
        )

        cols_to_drop = []
        for oris_id in oris_id_to_name_mapping.keys():
            if oris_id in oris_ids_in_results:
                df[oris_id_to_name_mapping[oris_id]] = (
                    df[f"{oris_id}-Points"].astype(str)
                    + " ("
                    + df[f"{oris_id}-Place"].astype(str)
                    + ")"
                )
                cols_to_drop.extend([f"{oris_id}-Points", f"{oris_id}-Place"])

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
        for category, group in df.groupby("category"):
            group_df = group.set_index("place", drop=True)
            results[category] = group_df.drop(columns=["category"])
    finally:
        return render_template(
            "results.html", seasons=seasons, season=season, results=results
        )


# Event
@app.route("/<string:season>/event/<string:event_id>/")
def event(season: str, event_id: str) -> str | Response:
    ev = em.get_event(season, event_id)
    if ev:
        return render_template("event.html", event_data=ev.to_dict())
    else:
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
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
