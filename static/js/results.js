/* Season standings: sorting, filtering by name, and keeping the page a
 * sensible length without hiding anyone.
 *
 * Every runner is in the HTML. Each category shows its first rows and offers
 * the rest behind a button, so the page opens short, but a search still finds
 * the 190th runner in H without a round trip - which matters at a race, where
 * the phone signal is whatever the car park has.
 *
 * Without JavaScript nothing is hidden and nothing is sorted: the table
 * arrives in standings order, which is the order that matters most.
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

    /* A race cell reads "182 (3.)", or "0 (DISK)", or the missing marker.
     * Sorting on the points is what people mean by sorting on a race: it
     * ranks the field, and a disqualification belongs at the bottom next to
     * the people who did not run it. */
    function numberIn(text) {
        const match = text.match(/-?\d+/);
        return match ? parseInt(match[0], 10) : null;
    }

    const input = document.getElementById('runner-filter');
    const sections = Array.from(document.querySelectorAll('.results-category'));
    if (!sections.length) {
        return;
    }

    const groups = sections.map(function (section) {
        const rows = Array.from(section.querySelectorAll('tbody tr'));
        return {
            section: section,
            body: section.querySelector('tbody'),
            rows: rows,
            // The order the server sent, which is the standings order.
            standings: rows.slice(),
            headers: Array.from(section.querySelectorAll('thead th')),
            // Folded once, not on every keystroke: hundreds of these.
            names: rows.map(function (row) {
                const cell = row.querySelector('.col-name');
                return fold(cell ? cell.textContent : '');
            }),
            // Where each row started, so a filter can find its folded name
            // after sorting has moved it.
            index: new Map(rows.map(function (row, i) { return [row, i]; })),
            button: section.querySelector('[data-show-all]'),
            expanded: false,
            sortIndex: 0,
            reversed: false,
            select: null,
        };
    });

    function cellText(row, index) {
        const cell = row.children[index];
        return cell ? cell.textContent.trim() : '';
    }

    function sortRows(group) {
        const index = group.sortIndex;
        const kind = group.headers[index]
            ? group.headers[index].querySelector('button')
            : null;
        const mode = kind ? kind.dataset.sort : 'rank';

        if (mode === 'rank' && !group.reversed) {
            group.rows = group.standings.slice();
            return;
        }

        const decorated = group.rows.map(function (row, position) {
            return { row: row, position: position };
        });

        decorated.sort(function (a, b) {
            const left = numberIn(cellText(a.row, index));
            const right = numberIn(cellText(b.row, index));
            if (left === null && right === null) {
                // Ties keep the standings order rather than shuffling.
                return a.position - b.position;
            }
            // A race somebody did not run sorts last either way round,
            // because "no result" is not a low score.
            if (left === null) {
                return 1;
            }
            if (right === null) {
                return -1;
            }
            return right - left || a.position - b.position;
        });

        group.rows = decorated.map(function (entry) {
            return entry.row;
        });
        if (group.reversed) {
            group.rows.reverse();
        }
    }

    function render() {
        const needle = input ? fold(input.value.trim()) : '';
        const searching = needle.length > 0;

        groups.forEach(function (group) {
            let shown = 0;
            group.rows.forEach(function (row) {
                const original = group.index.get(row);
                const matches = !searching || group.names[original].includes(needle);
                // While searching, every match is shown wherever it ranks.
                const withinLimit =
                    searching || group.expanded || shown < VISIBLE_BY_DEFAULT;
                row.hidden = !(matches && withinLimit);
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

            // Re-append in the current order. Appending a node that is already
            // in the document moves it, so this needs no removal pass.
            group.rows.forEach(function (row) {
                group.body.appendChild(row);
            });
        });
    }

    function modeOf(group, index) {
        const header = group.headers[index];
        const button = header ? header.querySelector('button') : null;
        return button ? button.dataset.sort : 'rank';
    }

    /* Points sort best-first and names A-Z, so "natural" differs by column.
       aria-sort has to report the direction the values actually end up in,
       not which way the flag happens to point. */
    function announce(group) {
        const naturallyDescending = modeOf(group, group.sortIndex) === 'race';
        const descending = naturallyDescending !== group.reversed;
        group.headers.forEach(function (header) {
            header.removeAttribute('aria-sort');
        });
        const active = group.headers[group.sortIndex];
        if (active) {
            active.setAttribute('aria-sort', descending ? 'descending' : 'ascending');
        }
    }

    function applySort(group, index, allowToggle) {
        if (allowToggle && group.sortIndex === index) {
            group.reversed = !group.reversed;
        } else {
            group.sortIndex = index;
            group.reversed = false;
        }
        if (group.select) {
            group.select.value = String(index);
        }
        announce(group);
        sortRows(group);
        render();
    }

    /* The card layout hides the table header, so there is nothing to click.
       Built from the header buttons rather than the template, so the labels
       cannot drift from the columns - and so it only exists when the sorting
       it drives exists. */
    function buildSortControl(group) {
        const overall = [];
        const races = [];
        group.headers.forEach(function (header, index) {
            const button = header.querySelector('button');
            if (!button) {
                return;
            }
            const entry = {
                index: index,
                label: button.dataset.sortLabel || button.textContent.trim(),
            };
            (button.dataset.sort === 'race' ? races : overall).push(entry);
        });
        const table = group.section.querySelector('table');
        if (!races.length || !table) {
            return;
        }

        const wrap = document.createElement('div');
        wrap.className = 'sort-control';

        const select = document.createElement('select');
        select.id = 'sort-' + group.section.id;

        const label = document.createElement('label');
        label.setAttribute('for', select.id);
        label.textContent = 'Seřadit podle';

        function option(entry) {
            const el = document.createElement('option');
            el.value = String(entry.index);
            el.textContent = entry.label;
            return el;
        }

        overall.forEach(function (entry) {
            select.appendChild(option(entry));
        });

        /* The races go in a group rather than the standings being emboldened:
           a font-weight on a single <option> is honoured by some browsers and
           silently dropped by others, while an <optgroup> label is styled by
           every one of them and says what the separation means. */
        const group_ = document.createElement('optgroup');
        group_.label = 'Jednotlivé závody';
        races.forEach(function (entry) {
            group_.appendChild(option(entry));
        });
        select.appendChild(group_);

        select.value = String(group.sortIndex);
        select.addEventListener('change', function () {
            applySort(group, parseInt(select.value, 10), false);
        });

        wrap.appendChild(label);
        wrap.appendChild(select);
        group.section.insertBefore(wrap, table);
        group.select = select;
    }

    groups.forEach(function (group) {
        buildSortControl(group);

        group.headers.forEach(function (header, index) {
            const button = header.querySelector('button');
            if (!button) {
                return;
            }
            button.addEventListener('click', function () {
                applySort(group, index, true);
            });
        });

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
