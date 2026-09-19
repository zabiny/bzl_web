"""
Site naming, organiser and partners, read from ``data/site.json``.

The league is named after whoever is sponsoring it, and sponsors come and go.
That name used to be written into two dozen places across the templates - page
titles, the header, the footer, the Open Graph tags, the rules page - so
dropping or changing a partner meant hunting through the markup.

It lives in the data directory rather than next to the code so that it is
mounted as a volume in production: renaming the league or removing a partner is
a file edit and a restart, not a rebuild.
"""

import json
import logging
from typing import Any

from src.paths import data_dir

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "site.json"

#: Used when data/site.json is missing or unreadable, so the site still renders.
DEFAULTS: dict[str, Any] = {
    "title": "Brněnská zimní liga",
    "short_title": "BZL",
    "tagline": "Zimní seriál závodů v orientačním běhu · Brno",
    "description": (
        "Brněnská zimní liga je zimní seriál závodů v orientačním běhu v Brně "
        "a okolí. Kalendář závodů, průběžné výsledky a novinky."
    ),
    "url": "https://bzl.zabiny.club",
    "contact_email": "poradatel@zabiny.club",
    "og_image": "og-image.png",
    "organizer": {
        "name": "SK Brno Žabovřesky",
        "url": "https://zabiny.club",
        "logo": "logos/zbm_large.png",
    },
    "partners": [],
}


def load_site_config() -> dict[str, Any]:
    """
    Read the site configuration.

    Returns
    -------
    The configuration, with any missing key filled in from :data:`DEFAULTS` and
    a ``main_partner`` shortcut for the first partner (or ``None``). Never
    raises: a missing or broken file falls back to the defaults, because a
    typo in it should not take the whole site down.

    """
    path = data_dir() / CONFIG_FILENAME
    loaded: dict[str, Any] = {}
    try:
        with path.open(encoding="utf-8") as f:
            parsed = json.load(f)
        if isinstance(parsed, dict):
            loaded = parsed
        else:
            logger.error("%s must contain a JSON object.", path)
    except FileNotFoundError:
        logger.info("No %s; using default site configuration.", path)
    except (OSError, ValueError) as e:
        logger.error("Could not read %s: %s", path, e)

    config = {**DEFAULTS, **loaded}
    partners = config.get("partners") or []
    config["partners"] = partners
    config["main_partner"] = partners[0] if partners else None
    return config
