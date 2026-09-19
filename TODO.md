# Where things stand

Working notes for picking this up again. Written 2026-09-19.

Branch **`pre-26-27-redesign`**, 19 commits ahead of `master`, **nothing pushed**.
Working tree clean. `pytest` (163 tests), `ruff check`, `ruff format --check` and
`mypy` all pass; the production image builds and serves.

The season 25/26 is over. The next one has not been set up yet, and the redesign
this branch is named after has not been started — what happened instead was a
pass over the existing site, fixing things that were broken and putting tests,
CI and documentation underneath it.

---

## Look at it

```bash
docker compose up -d --build     # http://localhost:5099
docker compose logs -f           # watch it
docker compose down              # stop
```

Content is mounted, so editing anything under `data/` or `templates/news/` then
`docker compose restart web` is enough — no rebuild. Code changes do need
`--build`.

Without Docker:

```bash
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
python app.py                    # http://localhost:5000
```

Pages worth looking at: `/news`, `/info`, `/25-26/calendar`, `/25-26/results`,
and an event with coordinates such as `/25-26/event/omikron/`.

**Maps need a key.** Without `MAPY_API_KEY` set, event pages show a link to
Mapy.com instead of a map. See the first open item.

---

## Open

### 1. Get a Mapy.com API key — the maps are still not visible without it

The old `api.mapy.cz/loader.js` is dead and the event pages were rendering an
empty grey box. They now use Leaflet with Mapy.com tiles, but that needs a free
key:

1. Sign in at <https://developer.mapy.com/account/> with a Seznam account.
2. Create an API project; the key is created with it, no approval needed.
3. Put it in `.env` (copy `.env.example`), or in the environment of wherever the
   site actually runs.

Free tier is 250 000 credits a month, one map tile is one credit. A busy race
weekend is nowhere near that.

Until this is done the map fix is invisible, so it is the first thing to do.

### 2. Nothing is pushed, and the deploy path is unknown

19 commits sit locally. Before pushing, work out how the site is actually built
and released, because it is **not** in this repository:

- No GitHub Actions workflow exists on `zabiny/bzl_web` (the API reports zero).
- No Jenkinsfile, no `.gitlab-ci`, no tags, no releases.
- The `origin/deploy` branch has not moved since November 2022.

So it is a webhook, something on the server, a registry build, or a workflow in
another repo. Whatever it is, it reacts to pushes rather than to workflow runs,
so the new `.github/workflows/ci.yml` should be inert — but that is reasoning,
not verification. **Find the deploy and write it down in the README.**

Also decide whether CI should skip routine content commits:

```yaml
on:
  push:
    paths-ignore: ['data/**', 'templates/news/**']
```

### 3. Two bits of Czech to check

- `templates/info.html`: "poukazy do **jeho e-obchodu**" — was "e-obchodu
  Sportegy". Changed because a template cannot decline the sponsor's name, but
  the grammar deserves a native eye.
- `templates/news/2024-10-01_sezona_zacina.html` writes "brněnské zimní ligy"
  in lower case while every other article capitalises it. That article predates
  Sportega becoming titular partner, so it may be deliberate. Left alone.

### 4. Set up season 26/27

```bash
mkdir -p data/26-27/events data/26-27/results
```

Then one JSON per race (schema in the README). Nothing else needs touching: the
navigation, the season dropdown and the "best N of M" sentence on the rules page
all read the newest season directory.

### 5. Smaller things, none urgent

- `docker/Dockerfile` installs `uv` and then uninstalls it in the same layer to
  keep it out of the image. A multi-stage build would be tidier.
- The `Gender` → `Sex` rename happened three commits after the code that
  introduced it, so six commits in the middle of the series mention `Gender`.
  Harmless, but a rebase would make the history read cleanly.
- The ORIS cache (`data/.oris_cache/`) is gitignored. A completely cold start
  with ORIS unreachable therefore hides the events that have no local name and
  date. Committing the cache would remove that gap, at the cost of some churn.
  Deliberately left out for now.

---

## Already decided — please do not re-open without a reason

- **Keep the per-sex podium in Z and V.** Asked and answered. It is the only
  reason the `Sex` column exists. Rationale and accuracy are in the README.
- **Do not regenerate the published standings of past seasons.** They cannot be
  byte-reproduced: they embedded human merge decisions that were never written
  down, and unregistered runners were keyed by an id that depended on the order
  the filesystem returned files in. 22 of those decisions were recovered into
  each season's `merge_decisions.json`; two could not be, because both runners
  were `nereg.` and nothing identifies them. New seasons are reproducible.
- **Version bumps are intentional**: pandas 2.2.3 → 3.0.6, Flask 3.0.3 → 3.1.3,
  gunicorn 23 → 26. The results pipeline was checked to produce identical values.

---

## Traps

- **`data/` permissions.** The container runs as uid 10001 and reads `data/`
  because it is world-readable. Tightening the host directory to `700` would
  break it.
- **The results calculator asks questions.** `overall <season>` prompts about
  duplicate runners the rules cannot resolve. Answers are saved to
  `merge_decisions.json` and replayed, so it only asks once. `--non-interactive`
  keeps ambiguous runners separate and warns instead.
- **Info page numbers are derived.** The "best N of M" sentence comes from the
  number of `is_bzl` races in the newest season, so adding a race changes it.

---

## Checks

```bash
pytest                                    # 163 tests, no network
ruff check . && ruff format --check .
mypy app.py src results_calculator
docker build -f docker/Dockerfile -t bzl_web .
```

The test suite uses its own fixture season and never touches `data/`, except
`tests/test_sex.py`, which deliberately measures the sex inference against every
runner in the published H and D tables and fails below 99% accuracy.
