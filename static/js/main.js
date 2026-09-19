/* Site-wide behaviour: the mobile navigation drawer.
 *
 * Hand-rolled rather than Bootstrap's collapse, because the drawer is the
 * only thing on the site that needed Bootstrap's JavaScript and this is
 * twenty lines. It also means the menu works before the CDN script arrives,
 * which on a slow phone at a race is exactly when someone opens the calendar.
 */
(function () {
    'use strict';

    const nav = document.getElementById('site-nav');
    const toggle = document.querySelector('[data-nav-open]');
    if (!nav || !toggle) {
        return;
    }

    function setOpen(open) {
        nav.classList.toggle('open', open);
        toggle.setAttribute('aria-expanded', String(open));
        if (open) {
            const first = nav.querySelector('[data-nav-close], a');
            if (first) {
                first.focus();
            }
        } else {
            toggle.focus();
        }
    }

    toggle.addEventListener('click', function () {
        setOpen(!nav.classList.contains('open'));
    });

    document.querySelectorAll('[data-nav-close]').forEach(function (el) {
        el.addEventListener('click', function () {
            setOpen(false);
        });
    });

    // Escape closes the drawer, and focus goes back to the button that opened
    // it. Stripping the class alone would leave aria-expanded lying about the
    // state, which is the bug the previous version had.
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && nav.classList.contains('open')) {
            setOpen(false);
        }
    });
})();
