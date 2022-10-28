from flask import Flask, render_template

from src.event import Event

app = Flask(__name__)


# Home
@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")


# Calendar
@app.route("/<string:season>/calendar")
def calendar(season: str):
    return render_template("calendar.html", season=season)


# Results
@app.route("/<string:season>/results")
def results(season: str):
    return render_template("results.html", season=season)


# Event
@app.route("/<string:season>/event/<string:event_id>/")
def event(season: str, event_id: str):
    ev: Event = Event.create_from_config(season, event_id)
    if ev:
        return render_template("event.html", event_data=ev.to_dict())
    else:
        return render_template("home.html")  # TODO: handle this better


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
