# Where things stand

Working notes for picking this up again. Written 2026-09-19.

Branch **`pre-26-27-redesign`**, 24 commits ahead of `master`, **nothing pushed**.
Working tree clean. `pytest` (199 tests), `ruff check`, `ruff format --check` and
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

The only open item that needs something from outside the repository, and the
one that makes the biggest visible difference. About five minutes:

1. Go to <https://developer.mapy.com/account/> and sign in with a Seznam account.
2. Create an API project. The key is generated with it — no approval, no card.
3. Put it in `.env` at the repository root (copy `.env.example`):

   ```
   MAPY_API_KEY=your-key-here
   ```

4. `docker compose up -d` — compose reads `.env` on its own. Open any event with
   coordinates, e.g. `/25-26/event/omikron/`, and the map should be there.
5. **Set the same variable on the server** — `.env` here only affects your own
   machine. See the deployment note below. Deploying without the key is safe:
   event pages fall back to a Mapy.com link, nothing breaks.

**The key is public.** It is a browser-side key: it goes into the page as a
`data-apikey` attribute and anyone viewing source can read it. That is how every
client-side map API works, but it means someone could spend your quota. Check
whether the Mapy console offers a domain or referrer restriction and, if it
does, restrict the key to `bzl.zabiny.club`. Free tier is 250 000 credits a
month and one tile is one credit — an interactive map view is roughly 10–20
tiles, so that is on the order of fifteen thousand map views a month. A club
site will not come close unless the key is being abused.

If you would rather the key never reach the browser at all, the alternative is
to proxy the tiles through Flask. That is more code, adds latency and puts tile
traffic through your server, and is almost certainly not worth it here.

### 2. Nothing is pushed, and the key has to reach the server

24+ commits sit locally.

What is known about the deployment, as of 2026-09-19:

- Pushing to `master` deploys to <https://bzl.zabiny.club>, pushing to `devel`
  to <https://dev.bzl.zabiny.club>.
- Both names resolve to `20.52.186.181`, which is also `azure.zabiny.club` — an
  Azure VM running Ubuntu with **nginx 1.18.0** in front of the container.
- `dev.bzl.zabiny.club` currently answers **502**, so nginx is configured for it
  but nothing is listening behind it.
- There is still **no GitHub Actions workflow** on the repository (the API
  reports zero), so whatever reacts to the push lives on that VM or in an
  external service, not in this repo.

Two things follow:

- **`MAPY_API_KEY` must be set on that VM**, not here. Where depends on how the
  container is started: a `.env` beside a `docker-compose.yml`, `-e` on a
  `docker run`, `Environment=` in a systemd unit, or a platform's settings page.
  Worth finding out and writing into the README.
- `docker-compose.yml` in this repo may or may not be what the server uses. If
  the VM starts the container some other way, that file is for local use only
  and the server's own configuration needs the same volumes (`./data`,
  `./templates/news`) to keep content editable without a rebuild.

### 3. ORIS — broken at the source, and moving domain

As of 2026-09-19 `oris.orientacnisporty.cz` serves a self-signed certificate
that expired on 11 January 2023, so nothing that verifies certificates can reach
it. This is being repaired at the ČSOS end; nothing to do here but wait.

Two things to pick up afterwards:

- **The API has moved.** `oris.ceskyorientak.cz` is the newer domain.
  `src/oris.py` still points at `https://oris.orientacnisporty.cz/API/`
  (`API_URL`, line 28). Once ORIS is healthy, check which host is canonical and
  change that one constant.
- **Nothing essential depends on ORIS any more.** Every 25/26 race now carries
  its own name and date, so the calendar and results are complete without it.
  ORIS only adds place, GPS, entry date and organiser. The older seasons are not
  backfilled yet — 25 races across 22/23, 23/24 and 24/25 still rely on ORIS for
  a name or a date, which is why their calendars look sparse when it is down.
  Worth doing while the live site still has the values, since those seasons are
  finished and will never change.

Do **not** add a certificate workaround. Trusting the certificate does not work
(expiry is checked separately from trust — tested), and pinning its fingerprint
would break the moment it is renewed.

### 4. Two bits of Czech to check

- `templates/info.html`: "poukazy do **jeho e-obchodu**" — was "e-obchodu
  Sportegy". Changed because a template cannot decline the sponsor's name, but
  the grammar deserves a native eye.
- `templates/news/2024-10-01_sezona_zacina.html` writes "brněnské zimní ligy"
  in lower case while every other article capitalises it. That article predates
  Sportega becoming titular partner, so it may be deliberate. Left alone.

### 5. Set up season 26/27

```bash
mkdir -p data/26-27/events data/26-27/results
```

Then one JSON per race (schema in the README). Nothing else needs touching: the
navigation, the season dropdown and the "best N of M" sentence on the rules page
all read the newest season directory.

### 6. Smaller things, none urgent

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
pytest                                    # 199 tests, no network
ruff check . && ruff format --check .
mypy app.py src results_calculator
docker build -f docker/Dockerfile -t bzl_web .
```

The test suite uses its own fixture season and never touches `data/`, except
`tests/test_sex.py`, which deliberately measures the sex inference against every
runner in the published H and D tables and fails below 99% accuracy.
