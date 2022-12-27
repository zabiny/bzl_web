import atexit
import locale
from datetime import date

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, url_for

from src.event_manager import EventManager

app = Flask(__name__)
em = EventManager()

# Update the EventManager every 10 mins
scheduler = BackgroundScheduler()
scheduler.add_job(func=em.update, trigger="interval", seconds=600)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


# Home
@app.route("/")
@app.route("/home")
def home():
    kid_year = date.today().year - 14 + (date.today().month > 6)
    vet_year = date.today().year - 45 + (date.today().month > 6)
    return render_template("home.html", kid_year=kid_year, vet_year=vet_year)


# Calendar
@app.route("/<string:season>/calendar")
def calendar(season: str):
    events = em.get_all_events(season, as_dicts=True)
    return render_template("calendar.html", season=season, events=events)


# Results
@app.route("/<string:season>/results")
def results(season: str):
    # Load results per category
    category_dfs = []
    for category in ["H", "D", "ZV", "HDD"]:
        df = pd.read_csv(f"data/{season}/results/overall_{category}.csv", index_col=0)
        df["category"] = category
        for place_col in df.filter(regex=r".*-Place"):
            if df[place_col].dtype == float:
                df[place_col] = df[place_col].apply(lambda x: f"{x:.0f}.")
        category_dfs.append(df)
    df = pd.concat(category_dfs)

    # Process DataFrame (rename and drop columns etc.)
    events = em.get_all_events(season)
    oris_id_to_name_mapping = {
        ev.oris_id: ev.name for ev in events.values() if ev.oris_id
    }

    oris_ids_in_results = set(
        [int(x.split("-")[0]) for x in df.columns if x[0].isdigit()]
    )

    cols_to_drop = []
    for oris_id in oris_ids_in_results:
        df[oris_id_to_name_mapping[oris_id]] = (
            df[f"{oris_id}-Points"].astype(str)
            + " ("
            + df[f"{oris_id}-Place"].astype(str)
            + ")"
        )
        cols_to_drop.extend([f"{oris_id}-Points", f"{oris_id}-Place"])

    best_n_col = df.filter(regex=r"Best.*").columns[0]
    n = best_n_col.split("-")[0][4:]
    df = df.rename(
        columns={
            best_n_col: f"Součet ({n} z {len(oris_ids_in_results)})",
            "Name": "Jméno",
        }
    ).drop(columns=cols_to_drop)

    # Split DataFrame per category
    results = {}
    for category, group in df.groupby("category"):
        results[category] = group.drop(columns=["category"])

    return render_template("results.html", season=season, results=results)


# Event
@app.route("/<string:season>/event/<string:event_id>/")
def event(season: str, event_id: str):
    ev = em.get_event(season, event_id)
    if ev:
        return render_template("event.html", event_data=ev.to_dict())
    else:
        return redirect(url_for("home"))


# jinja filters
@app.template_filter("day_from_date")
def _filter_day(input_date: date):
    if not input_date:
        return ""
    return input_date.strftime("%d")


@app.template_filter("month_and_year_from_date")
def _filter_month_and_year(input_date: date):
    if not input_date:
        return ""
    locale.setlocale(locale.LC_ALL, "cs_CZ")
    month_and_year = input_date.strftime("%b %Y")
    locale.resetlocale()
    return month_and_year


@app.template_filter("czech_date_from_date")
def _filter_czech_date(input_date: date):
    if not input_date:
        return ""
    czech_date = input_date.strftime("%d. %m. %Y")
    return czech_date


@app.template_filter("czech_date_from_datetime")
def _filter_date_from_datetime(input_datetime: str):
    if not input_datetime:
        return ""
    string_date, string_time = input_datetime.split()  # TODO: use time too
    d = date.fromisoformat(string_date)
    czech_date = d.strftime("%d. %m. %Y")
    return czech_date


@app.template_filter("full_season")
def _filter_full_season(season_short: str):
    year_from, year_to = season_short.split("-")
    return f"20{year_from} - 20{year_to}"


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
