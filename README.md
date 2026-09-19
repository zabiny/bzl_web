# BZL — Sportega Brněnská zimní liga

Website and results calculator for the **Sportega Brněnská zimní liga**, a winter
series of orienteering races in Brno, run by [SK Brno
Žabovřesky](https://zabiny.club). Live at **https://bzl.zabiny.club**.

A small Flask app that reads everything from files in `data/`, plus a CLI that
turns ORIS race results into season standings. There is no database.

---

## Contents

- [Quick start](#quick-start)
- [Running the site](#running-the-site)
- [Everyday jobs](#everyday-jobs) — the things you actually do during a season
  - [Publish results after a race](#publish-results-after-a-race)
  - [Add or change a race](#add-or-change-a-race)
  - [Post a news item](#post-a-news-item)
  - [Start a new season](#start-a-new-season)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Development](#development)
- [Things worth knowing](#things-worth-knowing)

---

## Quick start

```bash
git clone git@github.com:zabiny/bzl_web.git
cd bzl_web

python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

python app.py          # http://localhost:5000
```

`pytest` should pass out of the box.

## Running the site

### Docker (how it runs in production)

```bash
cp .env.example .env     # then put your Mapy.com API key in it
docker compose up -d --build
```

The site listens on port **5099**. `data/` and `templates/news/` are mounted as
volumes, so **publishing results or adding a news item does not need an image
rebuild** — change the files and `docker compose restart web`.

### Without Docker

```bash
gunicorn --conf ./docker/gunicorn.conf.py --bind 0.0.0.0:5099 app:app
```

---

## Everyday jobs

### Publish results after a race

Two commands. Say the race has ORIS id `9690` and the season is `25-26`:

```bash
# 1. Pull the race results from ORIS and convert placings into BZL points.
python -m results_calculator race 9690 -o data/25-26/results

# 2. Recompute the season standings from every points_*.csv in that folder.
python -m results_calculator overall 25-26
```

Then commit `data/25-26/results/` and restart the site.

**About the questions in step 2.** The calculator merges runners who appear
twice (a changed club, a missing registration number) using a cascade of rules.
When the rules cannot decide, it shows you the candidates and asks. Your answer
is saved in `data/<season>/results/merge_decisions.json`, so **it only asks
once** — later runs replay the recorded answer and produce identical standings.

Add `--non-interactive` to run unattended (in a script, say). Anything it cannot
decide is left as separate runners and reported as a warning; run it once
interactively afterwards to settle those properly.

Unregistered runners whose year of birth you know go in `data/known_unregs.json`
— that is what lets the calculator put them in the right Z/V category.

### Add or change a race

One JSON file per race in `data/<season>/events/<event_id>.json`. The file name
is the event's URL, so `kauflauf.json` becomes `/25-26/event/kauflauf/`.

```json
{
    "name": "Kauflauf",
    "date": "2026-03-15",
    "oris_id": 9690,
    "difficulty": "medium",
    "is_bzl": false,
    "desc_short": "Městská klasika na vylepšených Mapy.cz",
    "desc_long": [
        "První odstavec.",
        "Druhý odstavec — každý prvek seznamu je samostatný odstavec."
    ],
    "web": "https://kauflauf.adamna.net/",
    "organizer": "KOS TJ Tesla Brno",
    "organizer_logo": "tbm.gif"
}
```

| Field | Required | Notes |
|---|---|---|
| `desc_short` | yes | One line, shown in the calendar |
| `is_bzl` | yes | `true` counts towards the standings and gets a number in the calendar |
| `difficulty` | yes | `easy`, `medium` or `hard` |
| `oris_id` | see note | If set, name/date/place/GPS/organiser are filled in from ORIS |
| `name`, `date` | see note | Required **only** when there is no `oris_id` |
| `desc_long` | no | String, or a list of strings for several paragraphs |
| `place_desc`, `gps_lat`, `gps_lon` | no | Usually come from ORIS; set them to override |
| `web` | no | Defaults to the ORIS page |
| `organizer`, `organizer_logo`, `organizer_logo_large` | no | Logo file names from `static/images/logos/` |
| `images`, `video_yt_id` | no | Extra media on the event page |

**Anything you set here wins over ORIS.** The app re-reads `data/` every 10
minutes, so a change appears without a restart.

### Change the league name, the sponsor or the organiser

All of it lives in `data/site.json`:

```json
{
    "title": "Sportega Brněnská zimní liga",
    "short_title": "Sportega BZL",
    "description": "...",
    "contact_email": "poradatel@zabiny.club",
    "og_image": "og-image.png",
    "organizer": { "name": "...", "url": "...", "logo": "logos/zbm_large.png" },
    "partners": [
        { "name": "Sportega", "url": "https://www.sportega.cz/", "logo": "Sportega_logo_rgb_DarkBlue.png" }
    ]
}
```

The name appears in the page titles, the header, the footer, the rules page
and the link-preview tags; it is written once here. Dropping a sponsor is
`"partners": []` — their logos disappear from the header and footer, and the
paragraph on the rules page about e-shop vouchers goes with them. Logo paths
are relative to `static/images/`.

This file is inside the mounted data volume, so a change needs a restart, not
a rebuild. Old news items still name the sponsor of their time, which is as it
should be — they are a record of what happened.

### Post a news item

Drop an HTML fragment into `templates/news/`, named `YYYY-MM-DD_slug.html`. The
date in the file name is the publication date and sets the order; the first
`<h2>` is the headline.

```html
<h2 class="mb-3 mt-5">Sezóna začíná</h2>
<p>První závod se koná ...</p>
```

Bootstrap classes are available. These files are rendered as Jinja templates, so
`{{ ... }}` and `{% ... %}` are evaluated — keep that in mind if you ever need a
literal brace.

### Start a new season

```bash
mkdir -p data/26-27/events data/26-27/results
```

Add the event JSON files. That is all — the navigation, the season dropdown and
the rules page all pick up the newest season directory automatically, and the
"best N of M" sentence on the rules page is computed from the number of BZL
races in it.

---

## Configuration

All optional, all environment variables.

| Variable | Default | What it does |
|---|---|---|
| `MAPY_API_KEY` | *(empty)* | Mapy.com key for the map on each event page. Without it the page shows a link to Mapy.com instead. Free key: <https://developer.mapy.com/account/> |
| `BZL_DATA_DIR` | `data` | Where the seasons live |
| `BZL_ORIS_CACHE_DIR` | `<data>/.oris_cache` | Cached ORIS responses |
| `BZL_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `BZL_DISABLE_SCHEDULER` | unset | `1` turns off the background ORIS refresh (used by the tests) |
| `BZL_DEBUG` | unset | `1` enables the Flask reloader and debugger in `python app.py` |

---

## Project layout

```
app.py                     Flask routes, template filters, error pages
src/
  event.py                 One race: its config plus whatever ORIS knows
  event_manager.py         Loads all seasons, keeps them refreshed
  oris.py                  ORIS API client with an on-disk fallback cache
  results.py               Builds the tables and medals for the results page
  news.py                  Reads templates/news/
  site_config.py           League name, organiser and partners
  paths.py                 Where the data lives
results_calculator/        Standalone CLI, imports no Flask
  race.py                  ORIS results -> points_<id>.csv
  overall.py               points_*.csv -> overall_<category>.csv
  sex.py                   Sex, for medals in the mixed Z and V categories
  decisions.py             Remembers duplicate-runner answers
data/
  site.json                League name, organiser, partners
data/<season>/
  events/*.json            One file per race
  results/points_*.csv     Per-race points
  results/overall_*.csv    Season standings, one per category
  results/merge_decisions.json   Recorded duplicate-runner answers
templates/, static/        Jinja templates and assets
tests/                     pytest suite
```

### Categories

`H` men · `D` women · `HDD` children with a parent · `ZV` beginners, split by
the calculator into `Z` (youth) and `V` (veterans) from the year of birth in the
registration number. The age cut-offs move on 1 July each year.

### Scoring

1st 200, 2nd 190, 3rd 182, 4th 176, 5th 172, then `176 − place` down to 1 point
at 175th. A runner's total is their best `N` races, where `N` is just over half
the season's races (3 of 5, 4 of 7).

---

## Development

```bash
pytest                                   # tests
ruff check . && ruff format --check .    # lint and formatting
mypy app.py src results_calculator       # types
```

CI runs all of these on every pull request, and also builds the Docker image and
checks the container serves pages.

The tests use their own fixture season and never touch the network or the real
`data/` directory.

---

## Things worth knowing

**ORIS outages cannot take the site down.** The app starts from the event
configs plus a local cache and never blocks on the network; a background job
refreshes from ORIS every 10 minutes. Races that are more than two days past are
frozen in the cache and never fetched again, so a finished season costs no
requests at all.

**Maps need an API key.** Mapy.com retired the old `api.mapy.cz/loader.js` API
in 2024. The event pages now use Leaflet with Mapy.com tiles, which needs a free
key in `MAPY_API_KEY`. Their terms require the Mapy.com logo and copyright link
to stay visible on the map — `static/js/event-map.js` draws both; please leave
them in.

**Old seasons are not byte-reproducible.** Standings published before
`merge_decisions.json` existed embedded human choices that were never written
down, and unregistered runners were keyed by an id whose value depended on the
order the filesystem happened to return files in. The answers that could be
recovered have been written into each season's `merge_decisions.json`, but
re-running `overall` on a season from before 2026 can still produce small
cosmetic differences (column order, which temporary id an unregistered runner
gets). **Do not regenerate an old season's results unless you mean to.** New
seasons are fully reproducible.

**The `data/` directory is the content.** It is mounted into the container, so
results and news are file edits, not deployments.
