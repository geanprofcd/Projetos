(() => {
    const root = document.querySelector('[data-carousel]');
    if (!root) return;

    const track = root.querySelector('[data-carousel-track]');
    const slides = Array.from(root.querySelectorAll('[data-carousel-slide]'));
    const dots = Array.from(root.querySelectorAll('[data-carousel-dot]'));
    const prevButton = root.querySelector('[data-carousel-prev]');
    const nextButton = root.querySelector('[data-carousel-next]');
    const status = root.querySelector('[data-carousel-status]');

    if (!track || slides.length <= 1) return;

    const AUTOPLAY_MS = 4500;
    const SWIPE_THRESHOLD = 45;
    let index = 0;
    let autoplayId = null;
    let pointerStartX = null;
    let pointerStartY = null;

    const normalizedIndex = (value) => (value + slides.length) % slides.length;

    const render = (nextIndex, announce = false) => {
        index = normalizedIndex(nextIndex);
        track.style.transform = `translate3d(${-index * 100}%, 0, 0)`;

        slides.forEach((slide, slideIndex) => {
            const active = slideIndex === index;
            slide.classList.toggle('is-active', active);
            slide.setAttribute('aria-hidden', active ? 'false' : 'true');
        });

        dots.forEach((dot, dotIndex) => {
            const active = dotIndex === index;
            dot.classList.toggle('is-active', active);
            dot.setAttribute('aria-selected', active ? 'true' : 'false');
            dot.tabIndex = active ? 0 : -1;
        });

        if (status) {
            status.textContent = `Foto ${index + 1} de ${slides.length}`;
            if (announce) status.setAttribute('data-announced', String(Date.now()));
        }
    };

    const stopAutoplay = () => {
        if (autoplayId !== null) {
            window.clearInterval(autoplayId);
            autoplayId = null;
        }
    };

    const startAutoplay = () => {
        stopAutoplay();
        if (document.hidden) return;
        autoplayId = window.setInterval(() => render(index + 1), AUTOPLAY_MS);
    };

    const goTo = (nextIndex, announce = true) => {
        render(nextIndex, announce);
        startAutoplay();
    };

    prevButton?.addEventListener('click', () => goTo(index - 1));
    nextButton?.addEventListener('click', () => goTo(index + 1));

    dots.forEach((dot, dotIndex) => {
        dot.addEventListener('click', () => goTo(dotIndex));
        dot.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowRight') {
                event.preventDefault();
                const next = normalizedIndex(dotIndex + 1);
                dots[next]?.focus();
                goTo(next);
            } else if (event.key === 'ArrowLeft') {
                event.preventDefault();
                const previous = normalizedIndex(dotIndex - 1);
                dots[previous]?.focus();
                goTo(previous);
            }
        });
    });

    root.addEventListener('keydown', (event) => {
        if (event.target?.matches?.('[data-carousel-dot]')) return;
        if (event.key === 'ArrowRight') goTo(index + 1);
        if (event.key === 'ArrowLeft') goTo(index - 1);
    });

    root.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        pointerStartX = event.clientX;
        pointerStartY = event.clientY;
    });

    root.addEventListener('pointerup', (event) => {
        if (pointerStartX === null || pointerStartY === null) return;
        const dx = event.clientX - pointerStartX;
        const dy = event.clientY - pointerStartY;
        pointerStartX = null;
        pointerStartY = null;

        if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) <= Math.abs(dy)) return;
        goTo(dx < 0 ? index + 1 : index - 1);
    });

    root.addEventListener('pointercancel', () => {
        pointerStartX = null;
        pointerStartY = null;
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopAutoplay();
        else startAutoplay();
    });

    render(0);
    startAutoplay();
})();
