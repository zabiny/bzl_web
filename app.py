from flask import Flask, render_template

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


# Race
@app.route("/<string:season>/races/<int:race_id>/")
def race(season: str, race_id: int):
    return render_template("race.html")


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
