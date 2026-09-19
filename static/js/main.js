/* Site-wide behaviour: the mobile menu. */

// Close the mobile navigation with the Escape key.
//
// Goes through Bootstrap rather than stripping the class directly. Removing
// `.show` by hand hides the menu but leaves `aria-expanded="true"` on the
// toggler, so the button then tells screen readers the menu is open when it
// is not.
document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') {
        return;
    }
    const menu = document.querySelector('.navbar-collapse');
    if (!menu || !menu.classList.contains('show')) {
        return;
    }
    if (window.bootstrap && window.bootstrap.Collapse) {
        window.bootstrap.Collapse.getOrCreateInstance(menu).hide();
    } else {
        menu.classList.remove('show');
    }
});
