document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const menu = document.querySelector('.navbar-collapse');
        if (menu.classList.contains('show')) {
            menu.classList.remove('show');
        }
    }
});
