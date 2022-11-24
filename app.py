import atexit, math

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, url_for
from datetime import date

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
    zakYear = date.today().year - (14 - math.floor(date.today().month / 6))
    vetYear = date.today().year - (46 - math.floor(date.today().month / 6))
    return render_template("home.html", zakYear=zakYear, vetYear=vetYear)


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


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
