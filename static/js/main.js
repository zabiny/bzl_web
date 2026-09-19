/* Site-wide behaviour: mobile menu, snow background, and one small joke. */

// Close the mobile navigation with the Escape key.
document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') {
        return;
    }
    const menu = document.querySelector('.navbar-collapse');
    if (menu && menu.classList.contains('show')) {
        menu.classList.remove('show');
    }
});

// Falling snow. Skipped for visitors who asked for reduced motion, and if the
// library failed to load the page must still work.
document.addEventListener('DOMContentLoaded', function () {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion || typeof particlesJS === 'undefined') {
        return;
    }
    particlesJS.load('particles-js', '/static/js/particles.json');
});

// Easter egg: on roughly one page view in two hundred, every runner is replaced.
if (Math.random() < 0.005) {
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.runner-image').forEach(function (image) {
            image.src = '/static/images/runner8.svg';
        });
    });
}
