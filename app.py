"""Flask application serving the Sportega BZL website."""

import atexit
import logging
import os
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, abort, render_template, url_for
from werkzeug import Response
from werkzeug.utils import redirect

from results_calculator.overall import count_best_n
from results_calculator.race import hdd_max_year, zv_kid_year, zv_vet_year
from src.event_manager import EventManager
from src.news import load_news
from src.results import load_season_results
from src.site_config import load_site_config

logging.basicConfig(
    level=os.environ.get("BZL_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

#: How often to re-read the data directory and refresh events from ORIS.
REFRESH_INTERVAL_SECONDS = 600

#: Czech month abbreviations, used by the calendar. Hard-coded rather than
#: taken from the cs_CZ locale: locale.setlocale() changes process-global state
#: and is not thread-safe, and this app serves requests on several threads.
CZECH_MONTH_ABBREVIATIONS = (
    "led",
    "úno",
    "bře",
    "dub",
    "kvě",
    "čvn",
    "čvc",
    "srp",
    "zář",
    "říj",
    "lis",
    "pro",
)

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


def _require_season(season: str) -> None:
    """Abort with 404 for a season that does not exist, instead of a 500."""
    if not em.season_exists(season):
        abort(404)


@app.context_processor
def inject_globals() -> dict[str, object]:
    """Make the site configuration, seasons and year available to every template."""
    return {
        "site": load_site_config(),
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
    season = em.get_latest_season()
    total_races = em.count_bzl_races(season) if season else 0
    return render_template(
        "info.html",
        hdd_max_year=hdd_max_year(),
        zv_kid_year=zv_kid_year(),
        zv_vet_year=zv_vet_year(),
        total_races=total_races,
        counted_races=count_best_n(total_races),
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
    return render_template("news.html", news=load_news())


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
    _require_season(season)
    events = em.get_all_events(season, as_dicts=True)
    return render_template("calendar.html", season=season, events=events or {})


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
    _require_season(season)
    season_results = load_season_results(season, em.get_all_events(season) or {})
    return render_template(
        "results.html",
        season=season,
        results=season_results.tables if season_results else {},
        medals=season_results.medals if season_results else {},
    )


# Event
@app.route("/<string:season>/event/<string:event_id>/")
def event(season: str, event_id: str) -> str:
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
    Rendered HTML template for the event page.

    """
    ev = em.get_event(season, event_id)
    if ev is None:
        abort(404)
    return render_template(
        "event.html",
        event_data=ev.to_dict(),
        mapy_api_key=os.environ.get("MAPY_API_KEY", ""),
    )


@app.errorhandler(404)
def page_not_found(error: Exception) -> tuple[str, int]:
    """Render a friendly 404 page instead of Werkzeug's default."""
    return render_template("error.html", code=404, message="Stránka nenalezena."), 404


@app.errorhandler(500)
def internal_error(error: Exception) -> tuple[str, int]:
    """Render a friendly 500 page. The exception itself is logged by Flask."""
    return (
        render_template("error.html", code=500, message="Na serveru došlo k chybě."),
        500,
    )


# jinja filters
@app.template_filter("day_from_date")
def _filter_day(input_date: date | None) -> str:
    """Render the day of the month, e.g. ``"07"``."""
    if not input_date:
        return ""
    return input_date.strftime("%d")


@app.template_filter("month_and_year_from_date")
def _filter_month_and_year(input_date: date | None) -> str:
    """Render an abbreviated Czech month and the year, e.g. ``"led 2026"``."""
    if not input_date:
        return ""
    return f"{CZECH_MONTH_ABBREVIATIONS[input_date.month - 1]} {input_date.year}"


@app.template_filter("czech_date_from_date")
def _filter_czech_date(input_date: date | None) -> str:
    """Render a date the Czech way, e.g. ``"07. 01. 2026"``."""
    if not input_date:
        return ""
    return input_date.strftime("%d. %m. %Y")


@app.template_filter("czech_date_from_datetime")
def _filter_date_from_datetime(input_datetime: str | None) -> str:
    """Render the date part of an ORIS ``"YYYY-MM-DD HH:MM:SS"`` timestamp."""
    if not input_datetime:
        return ""
    string_date = str(input_datetime).split()[0]
    try:
        return date.fromisoformat(string_date).strftime("%d. %m. %Y")
    except ValueError:
        logger.warning("Could not parse date from %r.", input_datetime)
        return ""


@app.template_filter("full_season")
def _filter_full_season(season_short: str) -> str:
    """Expand ``"25-26"`` into ``"2025 - 2026"``."""
    parts = str(season_short).split("-")
    if len(parts) != 2:
        return str(season_short)
    return f"20{parts[0]} - 20{parts[1]}"


def main() -> None:
    """
    Run the Flask development server.

    Notes
    -----
    Production runs under gunicorn (see ``docker/gunicorn.conf.py``); this entry
    point is for local development only. Set ``BZL_DEBUG=1`` for the reloader
    and the interactive debugger.

    """
    app.run(port=5000, debug=os.environ.get("BZL_DEBUG") == "1")


if __name__ == "__main__":
    main()
