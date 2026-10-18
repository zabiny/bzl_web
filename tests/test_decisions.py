"""
Recorded duplicate-runner decisions.

Without these the standings cannot be recomputed: the calculator asks the same
questions again and a different answer silently produces different results.
"""

import json

import pandas as pd
import pytest

from results_calculator.decisions import MergeDecisions
from results_calculator.overall import (
    _apply_recorded_decision,
    _manual_decision_rule,
    _regno_to_index,
)


def _group(rows):
    """Build a duplicate group shaped like the calculator's internal frame."""
    frame = pd.DataFrame(
        rows, columns=["Name", "RegNo", "1-Place", "1-Points", "2-Place", "2-Points"]
    )
    frame["name_unified"] = "jagrova aneta"
    return frame


AMBIGUOUS = _group(
    [
        ["Jágrová Aneta", "PBM0954", "8.", 168, None, None],
        ["Jágrová Aneta", "RBK0951", None, None, "4.", 176],
    ]
)


def test_decisions_round_trip(tmp_path):
    path = tmp_path / "merge_decisions.json"
    decisions = MergeDecisions(path)
    decisions.record_merge("jagrova aneta", [["PBM0954", "RBK0951"]])
    decisions.record_separate("novak jan")
    decisions.save()

    reloaded = MergeDecisions(path)
    assert reloaded.get("jagrova aneta") == {
        "action": "merge",
        "groups": [["PBM0954", "RBK0951"]],
    }
    assert reloaded.get("novak jan") == {"action": "separate"}
    assert reloaded.get("nobody") is None


def test_nothing_is_written_when_no_decision_was_made(tmp_path):
    path = tmp_path / "merge_decisions.json"
    MergeDecisions(path).save()
    assert not path.exists()


def test_a_missing_file_is_not_an_error(tmp_path):
    assert MergeDecisions(tmp_path / "nope.json").get("anything") is None


def test_a_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "merge_decisions.json"
    path.write_text("{ broken", encoding="utf-8")
    assert MergeDecisions(path).get("anything") is None


def test_recorded_merge_is_replayed(tmp_path):
    decisions = MergeDecisions(tmp_path / "d.json")
    decisions.record_merge("jagrova aneta", [["PBM0954", "RBK0951"]])

    frames = _apply_recorded_decision(AMBIGUOUS, "jagrova aneta", decisions)
    merged = pd.concat(frames)

    assert len(merged) == 1, "the two entries are one person"
    assert merged.iloc[0]["RegNo"] == "PBM0954", "the first RegNo listed is kept"
    # Both race results survive the merge.
    assert merged.iloc[0]["1-Points"] == 168
    assert merged.iloc[0]["2-Points"] == 176


def test_recorded_separation_is_replayed(tmp_path):
    decisions = MergeDecisions(tmp_path / "d.json")
    decisions.record_separate("jagrova aneta")
    frames = _apply_recorded_decision(AMBIGUOUS, "jagrova aneta", decisions)
    assert len(pd.concat(frames)) == 2


def test_replay_does_not_depend_on_row_numbers(tmp_path):
    """Row labels shift between runs; registration numbers do not."""
    decisions = MergeDecisions(tmp_path / "d.json")
    decisions.record_merge("jagrova aneta", [["PBM0954", "RBK0951"]])

    shuffled = AMBIGUOUS.iloc[::-1].copy()
    shuffled.index = [77, 4]

    frames = _apply_recorded_decision(shuffled, "jagrova aneta", decisions)
    merged = pd.concat(frames)
    assert len(merged) == 1
    assert merged.iloc[0]["RegNo"] == "PBM0954"


def test_no_recorded_decision_falls_through(tmp_path):
    decisions = MergeDecisions(tmp_path / "d.json")
    assert _apply_recorded_decision(AMBIGUOUS, "jagrova aneta", decisions) is None


def test_a_runner_absent_this_season_is_skipped(tmp_path):
    decisions = MergeDecisions(tmp_path / "d.json")
    decisions.record_merge("jagrova aneta", [["PBM0954", "ZBM9999"]])
    frames = _apply_recorded_decision(AMBIGUOUS, "jagrova aneta", decisions)
    # Nothing to merge, so both are returned untouched rather than crashing.
    assert len(pd.concat(frames)) == 2


def test_duplicate_registration_numbers_cannot_be_replayed(tmp_path):
    unregistered = _group(
        [
            ["Novák Jan", "nereg.", "8.", 168, None, None],
            ["Novák Jan", "nereg.", None, None, "4.", 176],
        ]
    )
    assert _regno_to_index(unregistered) is None
    decisions = MergeDecisions(tmp_path / "d.json")
    decisions.record_merge("novak jan", [["nereg.", "nereg."]])
    assert _apply_recorded_decision(unregistered, "novak jan", decisions) is None


def test_non_interactive_keeps_ambiguous_runners_separate(tmp_path):
    decisions = MergeDecisions(tmp_path / "d.json")
    frames = _manual_decision_rule(
        AMBIGUOUS, "jagrova aneta", decisions, interactive=False
    )
    assert len(pd.concat(frames)) == 2
    assert decisions.get("jagrova aneta") is None, "a guess must not be recorded"


def test_the_prompt_records_what_the_operator_chose(tmp_path, monkeypatch):
    decisions = MergeDecisions(tmp_path / "d.json")
    monkeypatch.setattr("builtins.input", lambda *_: "0")
    frames = _manual_decision_rule(AMBIGUOUS, "jagrova aneta", decisions)
    assert len(pd.concat(frames)) == 1
    assert decisions.get("jagrova aneta") == {
        "action": "merge",
        "groups": [["PBM0954", "RBK0951"]],
    }


def test_the_prompt_records_a_separation(tmp_path, monkeypatch):
    decisions = MergeDecisions(tmp_path / "d.json")
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    _manual_decision_rule(AMBIGUOUS, "jagrova aneta", decisions)
    assert decisions.get("jagrova aneta") == {"action": "separate"}


def test_invalid_input_re_prompts_instead_of_crashing(tmp_path, monkeypatch):
    """`int('banana')` and out-of-range ids both used to raise."""
    answers = iter(["banana", "999", "1,1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    decisions = MergeDecisions(tmp_path / "d.json")
    frames = _manual_decision_rule(AMBIGUOUS, "jagrova aneta", decisions)
    assert len(pd.concat(frames)) == 1


def test_recorded_decisions_survive_a_save_and_reload_cycle(tmp_path, monkeypatch):
    path = tmp_path / "d.json"
    decisions = MergeDecisions(path)
    monkeypatch.setattr("builtins.input", lambda *_: "0")
    _manual_decision_rule(AMBIGUOUS, "jagrova aneta", decisions)
    decisions.save()

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["jagrova aneta"]["groups"] == [["PBM0954", "RBK0951"]]

    # A second run replays it without asking; input() would raise if called.
    def no_input(*_):
        raise AssertionError("must not prompt when a decision is recorded")

    monkeypatch.setattr("builtins.input", no_input)
    replayed = _apply_recorded_decision(
        AMBIGUOUS, "jagrova aneta", MergeDecisions(path)
    )
    assert len(pd.concat(replayed)) == 1


@pytest.mark.parametrize("answer", ["0", "1"])
def test_either_runner_can_be_chosen_as_the_main_one(tmp_path, monkeypatch, answer):
    decisions = MergeDecisions(tmp_path / "d.json")
    monkeypatch.setattr("builtins.input", lambda *_: answer)
    frames = _manual_decision_rule(AMBIGUOUS, "jagrova aneta", decisions)
    merged = pd.concat(frames)
    expected = AMBIGUOUS.loc[int(answer), "RegNo"]
    assert merged.iloc[0]["RegNo"] == expected
