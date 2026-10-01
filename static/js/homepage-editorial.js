
/**
 * RANGAM SARADHA SILKS — HOMEPAGE EDITORIAL CONTROLLER
 * Handles: Scroll-Reveal Intersection Observer, Navbar Scroll Transition,
 * Parallax Engine (Desktop only), Horizontal Category Track Controls.
 */

document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    initNavbarScroll();
    initContinuousTrack('categoryTrack', 'catTrackPrev', 'catTrackNext', 0.85);
    initContinuousTrack('productContinuousTrack', 'productTrackPrev', 'productTrackNext', 0.80);
    initContinuousTrack('dealsContinuousTrack', 'dealsTrackPrev', 'dealsTrackNext', 0.80);
    initHeroParallax();
    initHeroSlideSync();
});

/* ==========================================================================
   1. Scroll-Reveal Intersection Observer System
   ========================================================================== */
function initScrollReveal() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const revealTargets = document.querySelectorAll(
        '.editorial-reveal, .editorial-reveal-left, .editorial-reveal-right, .editorial-reveal-scale, .editorial-clip-reveal'
    );

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
        revealTargets.forEach(el => el.classList.add('is-revealed'));
        return;
    }

    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-revealed');
                observer.unobserve(entry.target);
            }
        });
    }, {
        root: null,
        rootMargin: '120px 0px 80px 0px',
        threshold: 0.01
    });

    revealTargets.forEach(el => revealObserver.observe(el));

    // Fail-safe: ensure all elements are visible even if user jumps or observer delays
    setTimeout(() => {
        revealTargets.forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.top < window.innerHeight + 200) {
                el.classList.add('is-revealed');
            }
        });
    }, 400);
}

/* ==========================================================================
   2. Navbar Scroll Smooth Transition
   ========================================================================== */
function initNavbarScroll() {
    const navbar = document.querySelector('.navbar-premium');
    if (!navbar) return;

    let ticking = false;

    const updateNavbar = () => {
        if (window.scrollY > 30) {
            navbar.classList.add('navbar-scrolled');
        } else {
            navbar.classList.remove('navbar-scrolled');
        }
        ticking = false;
    };

    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(updateNavbar);
            ticking = true;
        }
    }, { passive: true });

    // Initial check on page load
    updateNavbar();
}

/* ==========================================================================
   3. Continuous Auto-Scrolling Track Engine (Category & New Arrivals)
   ========================================================================== */
function initContinuousTrack(trackId, prevBtnId, nextBtnId, baseSpeed = 0.85) {
    const track = document.getElementById(trackId);
    if (!track) return;

    // Check item count: DO NOT scroll if 4 or fewer items!
    const items = Array.from(track.children);
    const prevBtn = prevBtnId ? document.getElementById(prevBtnId) : null;
    const nextBtn = nextBtnId ? document.getElementById(nextBtnId) : null;

    if (items.length <= 4) {
        if (prevBtn) prevBtn.style.display = 'none';
        if (nextBtn) nextBtn.style.display = 'none';
        return;
    }

    // Zero duplication: each item is shown exactly once (no "double time")

    let isPaused = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let resumeTimeout = null;
    let isResetting = false;

    const pause = () => { isPaused = true; };
    const resume = () => {
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && !isResetting) {
            isPaused = false;
        }
    };
    const delayedResume = (delay = 1800) => {
        clearTimeout(resumeTimeout);
        isPaused = true;
        resumeTimeout = setTimeout(() => {
            resume();
        }, delay);
    };

    // Pause on hover
    track.addEventListener('mouseenter', pause);
    track.addEventListener('mouseleave', resume);
    track.addEventListener('focusin', pause);
    track.addEventListener('focusout', resume);

    // Touch support (mobile/tablets)
    track.addEventListener('touchstart', pause, { passive: true });
    track.addEventListener('touchend', () => delayedResume(1500), { passive: true });

    // Drag-to-scroll support (desktop mouse)
    let isDragging = false;
    let startX = 0;
    let startScrollLeft = 0;
    let hasDragged = false;

    track.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isDragging = true;
        hasDragged = false;
        pause();
        startX = e.pageX - track.offsetLeft;
        startScrollLeft = track.scrollLeft;
        track.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX) * 1.5;
        if (Math.abs(walk) > 8) {
            hasDragged = true;
            track.scrollLeft = startScrollLeft - walk;
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            track.style.cursor = '';
            delayedResume(1500);
            setTimeout(() => { hasDragged = false; }, 80);
        }
    });

    // Prevent clicking inside item if drag occurred
    track.addEventListener('click', (e) => {
        if (hasDragged) {
            e.preventDefault();
            e.stopPropagation();
            hasDragged = false;
        }
    }, true);

    // Arrow navigation buttons
    if (prevBtn) {
        prevBtn.addEventListener('click', (e) => {
            e.preventDefault();
            track.scrollBy({ left: -340, behavior: 'smooth' });
            delayedResume(2500);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', (e) => {
            e.preventDefault();
            track.scrollBy({ left: 340, behavior: 'smooth' });
            delayedResume(2500);
        });
    }

    // Gentle Auto-Scroll loop (Smooth forward scroll -> pause at end -> smooth return -> repeat)
    let lastTime = performance.now();

    function step(now) {
        const delta = Math.min((now - lastTime) / 16.67, 2.5);
        lastTime = now;

        const maxScroll = track.scrollWidth - track.clientWidth;

        if (!isPaused && !isResetting && maxScroll > 15) {
            track.scrollLeft += baseSpeed * delta;

            // Reached the end of items
            if (track.scrollLeft >= maxScroll - 2) {
                isResetting = true;
                isPaused = true;

                // Pause for 2.5 seconds at the end so user sees all items
                setTimeout(() => {
                    track.scrollTo({ left: 0, behavior: 'smooth' });

                    // Pause 2 seconds at start before resuming forward scroll
                    setTimeout(() => {
                        isResetting = false;
                        resume();
                    }, 2000);
                }, 2500);
            }
        }

        requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}

/* ==========================================================================
   4. Subtle Parallax Engine (Desktop Only, High Performance)
   ========================================================================== */
function initHeroParallax() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion || window.innerWidth < 1024) return;

    const parallaxItems = document.querySelectorAll('.editorial-parallax-target');
    if (parallaxItems.length === 0) return;

    let ticking = false;

    const onScroll = () => {
        const scrolled = window.scrollY;
        parallaxItems.forEach(item => {
            const rect = item.getBoundingClientRect();
            // Only transform when element is near or in viewport
            if (rect.top < window.innerHeight && rect.bottom > 0) {
                const speed = parseFloat(item.getAttribute('data-parallax-speed')) || 0.08;
                const offset = (window.innerHeight - rect.top) * speed - 20;
                item.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
            }
        });
        ticking = false;
    };

    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(onScroll);
            ticking = true;
        }
    }, { passive: true });
}

/* ==========================================================================
   5. Hero Carousel Sync & Counter
   ========================================================================== */
function initHeroSlideSync() {
    const heroCarousel = document.getElementById('drapeHeroCarousel') || document.getElementById('editorialHeroCarousel');
    if (!heroCarousel) return;

    if (window.bootstrap && bootstrap.Carousel) {
        try {
            const bsCarousel = bootstrap.Carousel.getOrCreateInstance(heroCarousel, {
                interval: 5000,
                ride: 'carousel',
                wrap: true,
                pause: false,
                touch: true
            });
            bsCarousel.cycle();
        } catch (err) {
            console.debug('Carousel init:', err);
        }
    }

    heroCarousel.addEventListener('slide.bs.carousel', (e) => {
        // Sync active state on indicators
        const indicators = heroCarousel.querySelectorAll('.drape-carousel-indicators button, .carousel-indicators button');
        indicators.forEach((btn, idx) => {
            if (idx === e.to) {
                btn.classList.add('active');
                btn.setAttribute('aria-current', 'true');
            } else {
                btn.classList.remove('active');
                btn.removeAttribute('aria-current');
            }
        });

        const counterNums = document.querySelectorAll('.hero-counter-num');
        counterNums.forEach((num, idx) => {
            if (idx === e.to) {
                num.classList.add('active');
            } else {
                num.classList.remove('active');
            }
        });
    });
}
