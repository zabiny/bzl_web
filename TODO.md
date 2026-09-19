# Where things stand

Working notes for picking this up again. Written 2026-09-19.

Branch **`pre-26-27-redesign`**, pushed, open as **PR #77 into `devel`** —
<https://github.com/zabiny/bzl_web/pull/77>. CI is green (lint, format, types,
199 tests, and a container that builds and serves pages with no ORIS access).
Working tree clean.

Merging that PR deploys to <https://dev.bzl.zabiny.club>, not to production.

The season 25/26 is over. The next one has not been set up yet, and the redesign
this branch is named after has not been started — what happened instead was a
pass over the existing site, fixing things that were broken and putting tests,
CI and documentation underneath it.

---

## Look at it

```bash
docker compose -f docker-compose.local.yml up -d --build   # localhost:5099
docker compose -f docker-compose.local.yml logs -f
docker compose -f docker-compose.local.yml down
```

Content is mounted, so editing anything under `data/` or `templates/news/` then
restarting is enough — no rebuild. Code changes do need `--build`.

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

### 1. Mapy.com API key

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

### 2. Get the key into Coolify, then merge

PR #77 targets `devel`, so merging it releases to **dev.bzl.zabiny.club**;
production follows from a later merge into `master`.

What is known about the deployment, as of 2026-09-19:

- `master` deploys to <https://bzl.zabiny.club>, `devel` to
  <https://dev.bzl.zabiny.club>. Both resolve to `20.52.186.181`, also
  `azure.zabiny.club` — an Azure VM running Ubuntu with **nginx 1.18.0** in
  front of the container. The platform is **Coolify**, set up by a colleague.
- `dev.bzl.zabiny.club` answered **502** before any of this was pushed, so
  nginx is configured for it but nothing was listening behind it.
- The only GitHub Actions workflow on the repository is the CI added here, so
  whatever Coolify reacts to is a webhook or a poll, not a workflow.

To do, in order:

1. **Add `MAPY_API_KEY` in Coolify** — application, Environment Variables, as a
   *runtime* value, then redeploy. Without it the event pages show a link to
   Mapy.com instead of a map; nothing else is affected. The key already works
   locally.
2. **Merge #77 into `devel`** and look at dev.bzl.zabiny.club.
3. While in Coolify, note **which Build Pack** the application uses and whether
   **`data/` is mounted as a persistent volume**, and write both into the
   README. If `data/` is not mounted, publishing results still needs a redeploy
   — not a regression, but mounting it is the single biggest operational win
   left. The container writes nothing to `data/`; the ORIS cache lives in
   `/var/cache/bzl` and degrades to a warning if it is not writable.

### 3. ORIS — broken at the source, and moving domain

As of 2026-09-19 `oris.orientacnisporty.cz` serves a self-signed certificate
that expired on 11 January 2023, so nothing that verifies certificates can reach
it. This is being repaired at the ČSOS end; nothing to do here but wait.

One thing to pick up afterwards:

- **The API has moved.** `oris.ceskyorientak.cz` is the newer domain.
  `src/oris.py` still points at `https://oris.orientacnisporty.cz/API/`
  (`API_URL`, line 28). Once ORIS is healthy, check which host is canonical and
  change that one constant.
- **Nothing depends on ORIS any more.** All four seasons now carry their own
  names, dates, places, coordinates and organisers, harvested from the live site
  while it still held them. Every calendar renders identically to production
  with ORIS unreachable, and 35 of the 46 event pages draw a map; the other 11
  have no coordinates in ORIS either and show the Mapy.com link instead. ORIS is
  now enrichment for *new* races only.

Do **not** add a certificate workaround. Trusting the certificate does not work
(expiry is checked separately from trust — tested), and pinning its fingerprint
would break the moment it is renewed.

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
pytest                                    # 199 tests, no network
ruff check . && ruff format --check .
mypy app.py src results_calculator
docker build -f docker/Dockerfile -t bzl_web .
```

The test suite uses its own fixture season and never touches `data/`, except
`tests/test_sex.py`, which deliberately measures the sex inference against every
runner in the published H and D tables and fails below 99% accuracy.
