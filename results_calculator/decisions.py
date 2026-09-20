"""
Remembers how ambiguous duplicate runners were resolved.

Most possible duplicates are settled by the rule cascade in
:mod:`results_calculator.overall`, but some need a human: two registration
numbers, same name, same year of birth — one person who changed clubs, or two
people who happen to share a name.

Those answers used to exist only in the operator's head, which meant the
standings could not be recomputed: re-running the calculator asked the
questions again, and a different answer produced different results. Recording
them makes a season reproducible and lets the calculator run unattended.

Decisions are keyed by the normalised name and reference runners by
registration number, both of which are stable across runs (row positions are
not).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SEPARATE = "separate"
MERGE = "merge"


class MergeDecisions:
    """
    The recorded answers for one season, backed by a JSON file.

    Parameters
    ----------
    path
        File holding the decisions. It does not have to exist yet.

    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._decisions: dict[str, Any] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        try:
            with self.path.open(encoding="utf-8") as f:
                loaded = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            logger.warning("Could not read merge decisions from %s: %s", self.path, e)
            return
        if isinstance(loaded, dict):
            self._decisions = loaded

    def get(self, name_key: str) -> dict[str, Any] | None:
        """Return the recorded decision for a name, or None if there is none."""
        decision = self._decisions.get(name_key)
        return decision if isinstance(decision, dict) else None

    def record_separate(self, name_key: str) -> None:
        """Record that these runners are different people."""
        self._decisions[name_key] = {"action": SEPARATE}
        self._dirty = True

    def record_merge(self, name_key: str, groups: list[list[str]]) -> None:
        """
        Record that some runners are one person.

        Parameters
        ----------
        name_key
            The normalised name the decision applies to.
        groups
            One list of registration numbers per merged runner. The first entry
            of each list is the one whose name and number are kept.

        """
        self._decisions[name_key] = {"action": MERGE, "groups": groups}
        self._dirty = True

    def save(self) -> None:
        """Write the decisions back to disk if anything was added."""
        if not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(
                    dict(sorted(self._decisions.items())),
                    f,
                    ensure_ascii=False,
                    indent=4,
                )
                f.write("\n")
        except OSError as e:
            logger.warning("Could not save merge decisions to %s: %s", self.path, e)
            return
        logger.info("Recorded merge decisions in %s", self.path)
        self._dirty = False
