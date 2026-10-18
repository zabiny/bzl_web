/*
 * Map of an event centre, drawn with Leaflet on Mapy.com tiles.
 *
 * Mapy.com retired its own SMap/loader.js JS API; their current documented
 * approach is an open-source map library pointed at their REST tile endpoint,
 * with Leaflet as the recommended choice.
 * See https://developer.mapy.com/rest-api-mapy-cz/map-libraries/
 *
 * Attribution is mandatory under Mapy.com's terms: the clickable logo and the
 * copyright link below must both stay visible.
 */

(function () {
    'use strict';

    // "outdoor" is Mapy's tourist map: it shows paths and terrain, which is what
    // you actually want when looking for the start of an orienteering race.
    var MAPSET = 'outdoor';
    var TILE_URL = 'https://api.mapy.com/v1/maptiles/' + MAPSET + '/256/{z}/{x}/{y}?apikey={apikey}';
    var COPYRIGHT =
        '<a href="https://api.mapy.com/copyright" target="_blank" rel="noopener">&copy; Seznam.cz a.s. a další</a>';
    var LOGO_URL = 'https://api.mapy.com/img/api/logo.svg';
    var DEFAULT_ZOOM = 15;

    function buildLogoControl() {
        var LogoControl = L.Control.extend({
            options: { position: 'bottomleft' },
            onAdd: function () {
                var container = L.DomUtil.create('div', 'mapy-logo');
                var link = L.DomUtil.create('a', '', container);
                link.setAttribute('href', 'https://mapy.com/');
                link.setAttribute('target', '_blank');
                link.setAttribute('rel', 'noopener');
                var logo = L.DomUtil.create('img', '', link);
                logo.setAttribute('src', LOGO_URL);
                logo.setAttribute('alt', 'Mapy.com');
                L.DomEvent.disableClickPropagation(link);
                return container;
            }
        });
        return new LogoControl();
    }

    function initMap(container) {
        var lat = parseFloat(container.dataset.lat);
        var lon = parseFloat(container.dataset.lon);
        var apiKey = container.dataset.apikey;

        if (isNaN(lat) || isNaN(lon) || !apiKey) {
            container.hidden = true;
            return;
        }

        var map = L.map(container).setView([lat, lon], DEFAULT_ZOOM);

        L.tileLayer(TILE_URL.replace('{apikey}', encodeURIComponent(apiKey)), {
            minZoom: 0,
            maxZoom: 19,
            attribution: COPYRIGHT
        }).addTo(map);

        buildLogoControl().addTo(map);

        // The title and place come from the data attributes rather than from
        // interpolated JS string literals, so quotes in a place name cannot
        // break the script.
        var marker = L.marker([lat, lon]).addTo(map);
        var title = document.createElement('strong');
        title.textContent = container.dataset.title || '';
        var popup = document.createElement('div');
        popup.appendChild(title);
        if (container.dataset.place) {
            popup.appendChild(document.createElement('br'));
            popup.appendChild(document.createTextNode(container.dataset.place));
        }
        marker.bindPopup(popup).openPopup();
    }

    document.addEventListener('DOMContentLoaded', function () {
        var container = document.getElementById('map');
        if (!container || typeof L === 'undefined') {
            return;
        }
        try {
            initMap(container);
        } catch (error) {
            // A broken map must never take the rest of the page down with it.
            console.error('Map could not be initialised:', error);
            container.hidden = true;
        }
    });
})();
