document.addEventListener('click', (event) => {
    const back = event.target.closest('[data-back]');
    if (back) history.back();
});
document.addEventListener('submit', (event) => {
    if (event.target.matches('[data-confirm]') && !confirm(event.target.dataset.confirm)) {
        event.preventDefault();
    }
});

// Fade the fixed photograph over the first viewport of scrolling.
const backdrop = document.querySelector('[data-scroll-backdrop]');
if (backdrop) {
    let framePending = false;
    const updateBackdrop = () => {
        const availableScroll = document.documentElement.scrollHeight - window.innerHeight;
        const distance = Math.max(Math.min(window.innerHeight, availableScroll), 1);
        const progress = Math.min(Math.max(window.scrollY / distance, 0), 1);
        backdrop.style.opacity = String(1 - progress);
        framePending = false;
    };
    const scheduleBackdropUpdate = () => {
        if (!framePending) {
            framePending = true;
            window.requestAnimationFrame(updateBackdrop);
        }
    };
    window.addEventListener('scroll', scheduleBackdropUpdate, { passive: true });
    window.addEventListener('resize', scheduleBackdropUpdate);
    window.addEventListener('pageshow', scheduleBackdropUpdate);
    updateBackdrop();
}
