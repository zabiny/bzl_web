from flask import Flask, render_template

app = Flask(__name__)


# Home
@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")


def main():
    app.run(port=5000, debug=True)


if __name__ == "__main__":
    main()
