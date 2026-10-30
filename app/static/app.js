document.addEventListener('click', (event) => {
    const back = event.target.closest('[data-back]');
    if (back) history.back();
});
document.addEventListener('submit', (event) => {
    if (event.target.matches('[data-confirm]') && !confirm(event.target.dataset.confirm)) {
        event.preventDefault();
    }
});
