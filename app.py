import atexit, math
import locale
from datetime import date

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
    zak_year = date.today().year - 14 + (date.today().month < 6)
    vet_year = date.today().year - 46 + (date.today().month < 6)
    return render_template("home.html", zakYear=zak_year, vetYear=vet_year)


# Calendar
@app.route("/<string:season>/calendar")
def calendar(season: str):
    events = em.get_all_events(season, as_dicts=True)
    return render_template("calendar.html", season=season, events=events)


# Results
@app.route("/<string:season>/results")
def results(season: str):
    return render_template("results.html", season=season)


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


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
