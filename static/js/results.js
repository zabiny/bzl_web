/* Season standings: filtering by name, and keeping the page a sensible
 * length without hiding anyone.
 *
 * Every runner is in the HTML. Each category shows its first rows and offers
 * the rest behind a button, so the page opens short, but a search still finds
 * the 190th runner in H without a round trip - which matters at a race, where
 * the phone signal is whatever the car park has.
 *
 * Without JavaScript nothing is hidden: the truncation is an enhancement, not
 * a requirement.
 */
(function () {
    'use strict';

    const VISIBLE_BY_DEFAULT = 15;

    /* Czech names are full of diacritics and nobody types them into a search
     * box. Decomposing to NFD splits "á" into "a" plus a combining acute,
     * which the second step strips - so "adame" finds "Adámek", and "cerny"
     * finds "Černý". */
    function fold(text) {
        return text
            .normalize('NFD')
            .replace(/[̀-ͯ]/g, '')
            .toLowerCase();
    }

    const input = document.getElementById('runner-filter');
    const sections = Array.from(document.querySelectorAll('.results-category'));
    if (!sections.length) {
        return;
    }

    const groups = sections.map(function (section) {
        const rows = Array.from(section.querySelectorAll('tbody tr'));
        const button = section.querySelector('[data-show-all]');
        return {
            section: section,
            rows: rows,
            // Folded once, not on every keystroke: five categories of these.
            names: rows.map(function (row) {
                const cell = row.querySelector('.col-name');
                return fold(cell ? cell.textContent : '');
            }),
            button: button,
            expanded: false,
        };
    });

    function render() {
        const needle = input ? fold(input.value.trim()) : '';
        const searching = needle.length > 0;

        groups.forEach(function (group) {
            let shown = 0;
            group.rows.forEach(function (row, i) {
                const matches = !searching || group.names[i].includes(needle);
                // While searching, every match is shown wherever it ranks.
                const withinLimit =
                    searching || group.expanded || shown < VISIBLE_BY_DEFAULT;
                const visible = matches && withinLimit;
                row.hidden = !visible;
                if (matches) {
                    shown += 1;
                }
            });

            // A category nobody in it matches is worth collapsing entirely,
            // rather than leaving five empty headings to scroll past.
            group.section.hidden = searching && shown === 0;

            if (group.button) {
                group.button.hidden =
                    searching || group.rows.length <= VISIBLE_BY_DEFAULT;
            }
        });
    }

    groups.forEach(function (group) {
        if (!group.button) {
            return;
        }
        if (group.rows.length <= VISIBLE_BY_DEFAULT) {
            group.button.hidden = true;
            return;
        }
        group.button.hidden = false;
        group.button.addEventListener('click', function () {
            group.expanded = !group.expanded;
            group.button.textContent = group.expanded
                ? 'Zobrazit méně'
                : group.button.dataset.showAll;
            group.button.setAttribute('aria-expanded', String(group.expanded));
            render();
            if (!group.expanded) {
                group.section.scrollIntoView({ block: 'start' });
            }
        });
    });

    if (input) {
        input.addEventListener('input', render);
    }

    render();
})();
