import atexit
import locale
import logging
import os
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, url_for
from werkzeug import Response

from results_calculator.race import hdd_max_year, zv_kid_year, zv_vet_year
from src.event_manager import EventManager
from src.news import load_news
from src.results import load_season_results

logging.basicConfig(
    level=os.environ.get("BZL_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

#: How often to re-read the data directory and refresh events from ORIS.
REFRESH_INTERVAL_SECONDS = 600

app = Flask(__name__)
em = EventManager()


def _start_scheduler() -> BackgroundScheduler | None:
    """
    Start the background refresh of event data.

    The first run is scheduled immediately but still on the scheduler's thread,
    so that start-up never blocks on (or fails because of) ORIS. Set
    ``BZL_DISABLE_SCHEDULER=1`` to skip it entirely, which tests rely on so
    that they never touch the network.
    """
    if os.environ.get("BZL_DISABLE_SCHEDULER") == "1":
        logger.info("Background refresh disabled by BZL_DISABLE_SCHEDULER.")
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=em.update,
        trigger="interval",
        seconds=REFRESH_INTERVAL_SECONDS,
        id="event_manager_update",
        name="Update EventManager data",
        next_run_time=datetime.now(),
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    atexit.register(scheduler.shutdown)
    return scheduler


scheduler = _start_scheduler()


@app.context_processor
def inject_seasons() -> dict[str, object]:
    """Make the season list and current year available to every template."""
    return {
        "all_seasons": em.get_all_seasons(),
        "current_season": em.get_latest_season(),
        "current_year": date.today().year,
    }


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
        hdd_max_year=hdd_max_year(),
        zv_kid_year=zv_kid_year(),
        zv_vet_year=zv_vet_year(),
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
    season_results = load_season_results(season, em.get_all_events(season) or {})
    return render_template(
        "results.html",
        season=season,
        results=season_results.tables if season_results else {},
        medals=season_results.medals if season_results else {},
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
        return render_template(
            "event.html",
            event_data=ev.to_dict(),
            mapy_api_key=os.environ.get("MAPY_API_KEY", ""),
        )
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
