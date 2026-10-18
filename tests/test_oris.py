"""
The ORIS client must never take the website down.

These tests pin the failure that used to crash the app at import time: every
exception `requests` can raise has to be caught, and a cached copy served in
its place.
"""

import datetime
import json

import pytest
import requests

from src.oris import OrisClient


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


OK_PAYLOAD = {
    "Status": "OK",
    "Data": {
        "Name": "BZL: Testovací závod",
        "Date": "2027-01-10",
        "EntryDate1": "2027-01-07 23:59:59",
        "Place": 'Brno "centrum"',
        "GPSLat": "49.2101",
        "GPSLon": "16.5991",
        "Org1": {"Name": "SK Brno Žabovřesky"},
    },
}


@pytest.fixture
def client(tmp_path):
    return OrisClient(cache_dir=tmp_path / "cache")


def test_successful_fetch_is_normalised(client, monkeypatch):
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _Response(OK_PAYLOAD))
    data = client.get_event(1)
    assert data["name"] == "BZL: Testovací závod"
    assert data["date"] == datetime.date(2027, 1, 10)
    assert data["gps_lat"] == "49.2101"
    assert data["organizer"] == "SK Brno Žabovřesky"


def test_a_request_timeout_is_always_passed(client, monkeypatch):
    seen = {}

    def fake_get(*args, **kwargs):
        seen.update(kwargs)
        return _Response(OK_PAYLOAD)

    monkeypatch.setattr(client._session, "get", fake_get)
    client.get_event(1)
    assert seen.get("timeout"), "a request without a timeout can hang a worker forever"


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ConnectionError("down"),
        requests.exceptions.Timeout("slow"),
        requests.exceptions.SSLError("bad certificate"),
        requests.exceptions.HTTPError("500"),
        requests.exceptions.TooManyRedirects("loop"),
        requests.exceptions.ChunkedEncodingError("truncated"),
    ],
)
def test_every_requests_error_is_caught(client, monkeypatch, error):
    """These are the exceptions the old `except ConnectionError` did not catch."""

    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(client._session, "get", boom)
    assert client.get_event(1) is None


def test_malformed_json_is_caught(client, monkeypatch):
    class Broken(_Response):
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(client._session, "get", lambda *a, **k: Broken({}))
    assert client.get_event(1) is None


def test_an_oris_error_status_is_not_treated_as_data(client, monkeypatch):
    monkeypatch.setattr(
        client._session,
        "get",
        lambda *a, **k: _Response({"Status": "ERR", "Message": "no such event"}),
    )
    assert client.get_event(1) is None


def test_cached_data_is_served_when_oris_is_down(client, monkeypatch):
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _Response(OK_PAYLOAD))
    fresh = client.get_event(1)

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(client._session, "get", boom)
    cached = client.get_event(1)
    assert cached is not None
    assert cached["name"] == fresh["name"]
    assert cached["date"] == fresh["date"]


def test_offline_mode_never_makes_a_request(client, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("no request may be made with use_network=False")

    monkeypatch.setattr(client._session, "get", boom)
    assert client.get_event(1, use_network=False) is None


def test_past_events_are_never_refetched(client, monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return _Response(
            {**OK_PAYLOAD, "Data": {**OK_PAYLOAD["Data"], "Date": "2020-01-10"}}
        )

    monkeypatch.setattr(client._session, "get", counting_get)
    client.get_event(1)
    assert len(calls) == 1
    for _ in range(5):
        client.get_event(1)
    assert len(calls) == 1, "an event long past cannot change; it must stay cached"


def test_upcoming_events_are_refetched(client, monkeypatch):
    future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return _Response({**OK_PAYLOAD, "Data": {**OK_PAYLOAD["Data"], "Date": future}})

    monkeypatch.setattr(client._session, "get", counting_get)
    client.get_event(1)
    client.get_event(1)
    assert len(calls) == 2


def test_unchanged_data_does_not_rewrite_the_cache(client, monkeypatch):
    future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    payload = {**OK_PAYLOAD, "Data": {**OK_PAYLOAD["Data"], "Date": future}}
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _Response(payload))
    client.get_event(1)
    path = client._cache_path(1)
    first = path.read_text(encoding="utf-8")
    client.get_event(1)
    assert path.read_text(encoding="utf-8") == first


def test_a_corrupt_cache_file_is_ignored(client, monkeypatch):
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    client._cache_path(1).write_text("{not json", encoding="utf-8")

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(client._session, "get", boom)
    assert client.get_event(1) is None


def test_blank_gps_is_normalised_to_none(client, monkeypatch):
    payload = {
        "Status": "OK",
        "Data": {**OK_PAYLOAD["Data"], "GPSLat": "0", "GPSLon": ""},
    }
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _Response(payload))
    data = client.get_event(1)
    assert data["gps_lat"] is None
    assert data["gps_lon"] is None


def test_cache_survives_a_round_trip(client, monkeypatch, tmp_path):
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _Response(OK_PAYLOAD))
    client.get_event(1)
    stored = json.loads(client._cache_path(1).read_text(encoding="utf-8"))
    assert stored["date"] == "2027-01-10"

    reopened = OrisClient(cache_dir=client.cache_dir)
    restored = reopened.get_event(1, use_network=False)
    assert restored["date"] == datetime.date(2027, 1, 10)
