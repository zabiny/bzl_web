"""Site naming, organiser and partners, read from data/site.json."""

import json

import pytest

from src.site_config import DEFAULTS, load_site_config


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BZL_DATA_DIR", str(tmp_path))
    return tmp_path


def _write(data_dir, config):
    (data_dir / "site.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )


def test_values_are_read_from_the_file(data_dir):
    _write(data_dir, {"title": "Nová zimní liga", "short_title": "NZL"})
    config = load_site_config()
    assert config["title"] == "Nová zimní liga"
    assert config["short_title"] == "NZL"


def test_missing_keys_fall_back_to_defaults(data_dir):
    _write(data_dir, {"title": "Jen název"})
    config = load_site_config()
    assert config["title"] == "Jen název"
    assert config["contact_email"] == DEFAULTS["contact_email"]
    assert config["organizer"] == DEFAULTS["organizer"]


def test_a_missing_file_gives_the_defaults(data_dir):
    config = load_site_config()
    assert config["title"] == DEFAULTS["title"]
    assert config["partners"] == []


@pytest.mark.parametrize("content", ["{ broken", "[]", '"a string"', ""])
def test_a_broken_file_never_takes_the_site_down(data_dir, content):
    (data_dir / "site.json").write_text(content, encoding="utf-8")
    config = load_site_config()
    assert config["title"] == DEFAULTS["title"]


def test_main_partner_is_the_first_one(data_dir):
    _write(data_dir, {"partners": [{"name": "A"}, {"name": "B"}]})
    assert load_site_config()["main_partner"] == {"name": "A"}


def test_main_partner_is_none_when_the_sponsor_is_dropped(data_dir):
    _write(data_dir, {"partners": []})
    assert load_site_config()["main_partner"] is None


def test_partners_key_absent_is_treated_as_no_partners(data_dir):
    _write(data_dir, {"title": "Bez partnera"})
    config = load_site_config()
    assert config["partners"] == []
    assert config["main_partner"] is None
