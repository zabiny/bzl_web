# Where things stand

Working notes for picking this up again. Written 2026-09-19.

Branch **`pre-26-27-redesign`**, open as **PR #77 into `devel`** —
<https://github.com/zabiny/bzl_web/pull/77>. Merging it deploys to
<https://dev.bzl.zabiny.club>, not to production.

The redesign the branch is named after **has now been done**. Three pieces,
one commit each:

1. `7e212e9` — removed the broken decorative layer (runner silhouettes,
   particle starfield, Font Awesome) and the defects it was hiding.
2. `dbedc93` — `src/race_stats.py`: participant counts and per-category
   podiums, read from the per-race results files.
3. `0c44106` — the redesign itself: an ISOM map palette behind a two-layer
   token system, the calendar drawn as an orienteering course, and the
   standings rebuilt as cards on a phone, which removed jQuery, DataTables
   and FixedColumns.

The four candidate designs were judged on a canvas and **variant B, "Kurz"**,
was chosen: <https://claude.ai/artifact/BbxmizzuMVnzt5wPDfuKCP> (private —
share it from the page's Share menu if anyone else needs to see it).

The season 25/26 is over and 26/27 is not set up yet.

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

Pages worth looking at: `/25-26/calendar` (the course, and a finished race
expanded to its podium), `/25-26/results` (resize below 780px to see the
cards), `/news`, `/info`, and an event with coordinates such as
`/25-26/event/omikron/`.

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

### 3. ORIS — repaired, and the domain switched

Resolved on 2026-09-20. `oris.ceskyorientak.cz` is now canonical, serves a
valid certificate, and answers API calls; the code points at it.

Worth knowing why this mattered more than a rename: the old host still
answers, but it **301s every request to the new domain's root**, dropping the
path and the query string. An API call sent there comes back as the
homepage's HTML instead of JSON, so every lookup failed silently — the client
caught it, logged it and returned nothing, exactly as designed. Verified live
through `OrisClient` against a cold cache: names, dates, places, GPS and
organisers all come back.

The domain is defined once, in `src/oris.py` (`BASE_URL`). `API_URL` and
`event_url()` derive from it, `results_calculator/race.py` imports `API_URL`,
and the two prose links on the info page come from `oris_url` in the template
globals. It was in five places before; that is what made this worth doing
properly rather than with a search and replace.

**Nothing depends on ORIS anyway.** All four seasons carry their own names,
dates, places, coordinates and organisers, harvested while the old site still
held them, and local values win over ORIS. Every calendar renders identically
with ORIS unreachable. ORIS is enrichment for *new* races.

Do **not** add a certificate workaround if it breaks again. Trusting an
expired certificate does not work (expiry is checked separately from trust —
tested), and pinning a fingerprint would break the moment it is renewed.

### 4. Set up season 26/27

```bash
mkdir -p data/26-27/events data/26-27/results
```

Then one JSON per race (schema in the README). Nothing else needs touching: the
navigation, the season dropdown and the "best N of M" sentence on the rules page
all read the newest season directory.

### 5. Design follow-ups

The owner expects to find nits once the redesign has been lived with. Known
open questions, none blocking:

- **The course at full length.** It was designed against four races and now
  renders twelve. It holds, but nobody has looked at a full season on a phone
  for long.
- **The results page is still 344 KB** — down from 417 KB with the whole
  DataTables stack gone, but it renders 681 rows. If it ever feels slow,
  the fix is a route per category rather than paging.
- **Race podiums in Z and V are ranked by place, not split by sex**, unlike
  the season medals. The race was scored as one field per class, so a per-sex
  race podium would show a "winner" who did not get the winning points. Raised
  with the owner and left as is.
- **Dark mode** is designed for but not built: `tokens.css` section 6 holds
  the contract, and it is a re-valuing of section 2 alone.

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
- **The info page states the scoring rule, not a race count.** A season's
  number of races is not settled until the last one is confirmed, so the page
  explains "a strict majority of the season's races" and leaves the
  arithmetic to the results table, which counts what actually happened.
  `count_best_n` is still the single definition of the rule.

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
