"""End-to-end checks on the rendered pages."""

import re

import pytest


def _div_balance(html: str) -> int:
    return len(re.findall(r"<div\b", html)) - len(re.findall(r"</div>", html))


def _titles(html: str) -> list[str]:
    return re.findall(r"<title>(.*?)</title>", html, re.S)


@pytest.mark.parametrize(
    "url",
    ["/info", "/news", "/26-27/calendar", "/26-27/results"],
)
def test_pages_render(client, url):
    assert client.get(url).status_code == 200


def test_home_redirects_to_news(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/news" in response.headers["Location"]


@pytest.mark.parametrize(
    "url",
    [
        "/99-99/results",
        "/99-99/calendar",
        "/nonsense/results",
        "/nonsense/calendar",
        "/26-27/event/neexistuje/",
    ],
)
def test_unknown_urls_are_404_not_500(client, url):
    """These all used to raise, producing a 500 for anything a bot crawled."""
    response = client.get(url)
    assert response.status_code == 404
    assert "Stránka nenalezena" in response.get_data(as_text=True)


@pytest.mark.parametrize("event_id", ["s_mapou", "bez_mapy"])
def test_event_pages_have_balanced_markup(client, event_id):
    """Events without GPS used to leave two <div>s unclosed."""
    html = client.get(f"/26-27/event/{event_id}/").get_data(as_text=True)
    assert _div_balance(html) == 0


@pytest.mark.parametrize(
    "url", ["/info", "/news", "/26-27/calendar", "/26-27/event/s_mapou/"]
)
def test_pages_have_exactly_one_title(client, url):
    assert len(_titles(client.get(url).get_data(as_text=True))) == 1


def test_event_page_title_names_the_event(client):
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert "Závod s mapou" in _titles(html)[0]


def test_map_is_rendered_for_an_event_with_coordinates(client):
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert 'id="map"' in html
    assert "leaflet@1.9.4" in html
    assert "event-map.js" in html
    assert 'data-lat="49.2101"' in html


def test_the_dead_mapy_cz_api_is_gone(client):
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert "api.mapy.cz/loader.js" not in html
    assert "SMap" not in html


def test_no_map_markup_without_coordinates(client):
    html = client.get("/26-27/event/bez_mapy/").get_data(as_text=True)
    assert 'id="map"' not in html
    assert "leaflet" not in html


def test_a_link_to_mapy_replaces_the_map_when_no_api_key_is_set(client, monkeypatch):
    monkeypatch.setenv("MAPY_API_KEY", "")
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert 'id="map"' not in html
    assert "mapy.com" in html


def test_place_names_with_quotes_do_not_break_the_page(client):
    """The place goes into a data attribute, not a JS string literal."""
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert "&#34;Žabovřesky&#34;" in html or "&quot;Žabovřesky&quot;" in html


def test_multi_paragraph_descriptions_render_as_paragraphs(client):
    html = client.get("/26-27/event/s_mapou/").get_data(as_text=True)
    assert "<p>První odstavec.</p>" in html
    assert "<p>Druhý odstavec.</p>" in html


def test_calendar_shows_czech_months_without_the_locale(client):
    """locale.setlocale() was both thread-unsafe and a hard start-up dependency."""
    html = client.get("/26-27/calendar").get_data(as_text=True)
    assert "LED 2027" in html
    assert "ÚNO 2027" in html


def test_navigation_points_at_the_newest_season(client):
    html = client.get("/info").get_data(as_text=True)
    assert "/26-27/calendar" in html
    assert "/26-27/results" in html


def test_info_page_states_the_real_scoring_rule(client):
    html = client.get("/info").get_data(as_text=True)
    # The fixture season has two BZL races, so the best 2 of 2 count.
    assert "2 nejlepších závodů" in html
    assert "z 2 možných" in html


def test_results_page_marks_medals(client):
    html = client.get("/26-27/results").get_data(as_text=True)
    assert "medal-gold" in html
    assert "medal-silver" in html
    assert "medal-bronze" in html
    assert "table-warning" not in html


def test_results_season_selector_lists_the_seasons(client):
    html = client.get("/26-27/results").get_data(as_text=True)
    assert "2026 - 2027" in html


def test_event_content_is_escaped(client, flask_app):
    """Jinja autoescaping must stay on for data that comes from ORIS."""
    import app as app_module

    event = app_module.em.get_event("26-27", "bez_mapy")
    original = event.desc_short
    event.desc_short = "<img src=x onerror=alert(1)>"
    try:
        html = client.get("/26-27/event/bez_mapy/").get_data(as_text=True)
    finally:
        event.desc_short = original
    assert "<img src=x onerror" not in html
    assert "&lt;img src=x onerror" in html


def test_no_requests_for_deleted_stylesheets(client):
    html = client.get("/26-27/results").get_data(as_text=True)
    for dead in ("menuStyle", "infoStyle", "newsStyle"):
        assert dead not in html


def test_social_preview_image_is_hosted_locally(client):
    html = client.get("/news").get_data(as_text=True)
    assert "ubc.net" not in html
    assert "og-image.png" in html
