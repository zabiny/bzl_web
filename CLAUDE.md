# Notes for Claude

Flask site plus a results-calculator CLI for the Sportega Brněnská zimní liga, a
winter orienteering series in Brno. No database: everything is JSON and CSV
under `data/`, versioned in git.

**Read `TODO.md` first** — it holds the current state, what is still open, and
decisions that have already been made. `README.md` covers how to run things and
how to publish results.

## Checks

```bash
pytest
ruff check . && ruff format --check .
mypy app.py src results_calculator
```

All three run in CI. `ruff format` is authoritative; line length 88.

## Conventions

- Docstrings are numpydoc, on everything public. Match the surrounding density.
- Type hints throughout.
- Comments explain *why*, not what. Where a line exists because something once
  broke, the comment says so.
- Czech is the site's language. Keep user-facing strings in Czech and ask before
  rewriting existing Czech prose.

## Things to be careful with

- **Never regenerate `data/*/results/overall_*.csv` for a past season.** They
  cannot be byte-reproduced and they are published results people care about.
  `TODO.md` explains why. Adding a column by pure insertion is fine, if every
  other column is verified unchanged line by line.
- **`data/` is content, not code.** It is mounted as a volume in production, so
  results and news are file edits rather than deployments. Do not bake it in.
- **The site must start without ORIS.** `EventManager` loads from configs plus
  the on-disk cache and never blocks on the network; the background scheduler
  does the fetching. Anything that reintroduces a network call on the import
  path is a regression — this used to take the whole site down.
- **Catch `requests.exceptions.RequestException`**, never the same-named
  builtins. `requests.exceptions.ConnectionError` is not `ConnectionError`;
  they are siblings under `OSError`. That bug is what `src/oris.py` exists to
  prevent, and `tests/test_oris.py` pins it.
- **Branding lives in `data/site.json`.** The league is named after its sponsor
  and sponsors change. Do not hard-code the name in a template; there is a test
  that fails if you do.
- **No secrets in the repo.** `MAPY_API_KEY` comes from the environment.
- **No colour literal outside `static/style/tokens.css`**, and no component
  may reference a primitive token. Components use the semantic names only.
  That single rule is what makes dark mode a drop-in later; section 6 of
  tokens.css holds the contract. Two greps enforce it:

  ```bash
  grep -nE 'var\(--(isom|paper|ink|silver)-' static/style/{base,components,page-*}.css
  grep -nEi '#[0-9a-f]{3,8}|hsla?\(' static/style/{base,components,page-*}.css
  ```

  Both should return nothing. `currentColor`, `transparent` and `inherit` are
  fine, and so are the two `rgb(... / n%)` translucent overlays in
  `components.css`. Print colours are tokens too (`--print-ink`,
  `--print-paper`) rather than an exemption, because paper is white and ink
  is black however the screen is themed.
- **The calendar is drawn as an orienteering course.** Three conventions are
  load-bearing, because breaking any of them is what a competitor notices
  first: the start triangle's apex points along the line at the first race,
  the connecting line is **solid** (a dashed line is a marked route, symbol
  707), and the line never touches a symbol. Numbers inside the circles and
  a straight vertical line are deliberate simplifications. A race outside the
  league is a plain dot, never a smaller circle - a small circle reads as a
  control drawn badly.

## Layout

```
app.py                  routes, template filters, error pages
src/oris.py             ORIS API client + disk cache (never raises)
src/event_manager.py    loads seasons, background refresh
src/results.py          builds the results tables and medals
src/race_stats.py       per-race participant counts and podiums
src/site_config.py      league name, organiser, partners
results_calculator/     standalone CLI, imports no Flask
data/<season>/          events/*.json, results/*.csv
```
