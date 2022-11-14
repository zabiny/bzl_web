from flask import Flask, redirect, render_template, url_for

from src.event_manager import EventManager

app = Flask(__name__)
em = EventManager()


# Home
@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")


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
    ev = em.create_event_from_config(season, event_id)
    if ev:
        return render_template("event.html", event_data=ev.to_dict())
    else:
        return redirect(url_for("home"))


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
