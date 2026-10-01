/**
 * Rangam Saradha Silks - Product Showcase Interactive Controller
 * Handles gallery thumbnails, 5-second auto-slideshow, lightbox preview, interactive tabs, and quantity stepper
 */

document.addEventListener('DOMContentLoaded', function () {
    // ------------------------------------------------------------------------
    // 1. Gallery Thumbnail Switching & 5-Second Auto-Rotation
    // ------------------------------------------------------------------------
    const mainImg = document.getElementById('showcaseMainImg');
    const thumbItems = Array.from(document.querySelectorAll('.showcase-thumb-item'));
    const thumbsList = document.querySelector('.showcase-thumbs-list');
    const thumbsNavBtn = document.getElementById('showcaseThumbsNavBtn');
    const galleryLayout = document.querySelector('.showcase-gallery-layout');
    const mainImgWrapper = document.getElementById('showcaseMainImgWrapper');
    const lightboxImg = document.getElementById('showcaseLightboxImg');
    const lightboxModal = document.getElementById('showcaseLightboxModal');

    let currentIndex = 0;
    let autoSlideTimer = null;
    const SLIDE_INTERVAL_MS = 5000; // Auto-change every 5 seconds

    // Helper: switch showcase to a specific image index
    function switchToIndex(index, isAuto = false) {
        if (!thumbItems.length || !mainImg) return;

        // Wrap around bounds
        if (index < 0) {
            index = thumbItems.length - 1;
        } else if (index >= thumbItems.length) {
            index = 0;
        }
        currentIndex = index;

        const targetThumb = thumbItems[currentIndex];
        if (!targetThumb) return;

        const fullSrc = targetThumb.getAttribute('data-full-img');
        if (!fullSrc) return;

        // 1. Update active styling on thumbnails
        thumbItems.forEach((t, i) => {
            if (i === currentIndex) {
                t.classList.add('active');
            } else {
                t.classList.remove('active');
            }
        });

        // Scroll ONLY the thumbsList container internally without ever moving the window/page scroll position
        if (thumbsList && targetThumb) {
            const isHorizontal = thumbsList.scrollWidth > thumbsList.clientWidth && thumbsList.scrollHeight <= thumbsList.clientHeight;

            if (isHorizontal) {
                const thumbLeft = targetThumb.offsetLeft;
                const thumbRight = thumbLeft + targetThumb.offsetWidth;
                const listLeft = thumbsList.scrollLeft;
                const listRight = listLeft + thumbsList.clientWidth;

                if (thumbLeft < listLeft) {
                    thumbsList.scrollTo({ left: thumbLeft, behavior: 'smooth' });
                } else if (thumbRight > listRight) {
                    thumbsList.scrollTo({ left: thumbRight - thumbsList.clientWidth, behavior: 'smooth' });
                }
            } else {
                const thumbTop = targetThumb.offsetTop;
                const thumbBottom = thumbTop + targetThumb.offsetHeight;
                const listTop = thumbsList.scrollTop;
                const listBottom = listTop + thumbsList.clientHeight;

                if (thumbTop < listTop) {
                    thumbsList.scrollTo({ top: thumbTop, behavior: 'smooth' });
                } else if (thumbBottom > listBottom) {
                    thumbsList.scrollTo({ top: thumbBottom - thumbsList.clientHeight, behavior: 'smooth' });
                }
            }
        }

        // 2. Smooth fade transition to new image
        mainImg.style.opacity = '0.35';
        setTimeout(() => {
            mainImg.src = fullSrc;
            if (lightboxImg) {
                lightboxImg.src = fullSrc;
            }
            mainImg.style.opacity = '1';
        }, 120);
    }

    // Initialize currentIndex from any existing .active thumbnail
    const initialActiveIdx = thumbItems.findIndex(t => t.classList.contains('active'));
    if (initialActiveIdx !== -1) {
        currentIndex = initialActiveIdx;
    }

    // Auto-slide Timer Functions
    function startAutoSlide() {
        stopAutoSlide();
        // Only run auto-slide if there are multiple images
        if (thumbItems.length <= 1) return;

        autoSlideTimer = setInterval(() => {
            const nextIdx = (currentIndex + 1) % thumbItems.length;
            switchToIndex(nextIdx, true);
        }, SLIDE_INTERVAL_MS);
    }

    function stopAutoSlide() {
        if (autoSlideTimer) {
            clearInterval(autoSlideTimer);
            autoSlideTimer = null;
        }
    }

    function restartAutoSlide() {
        stopAutoSlide();
        startAutoSlide();
    }

    // Attach click and keyboard events to each thumbnail
    if (thumbItems.length > 0 && mainImg) {
        thumbItems.forEach((thumb, index) => {
            function onThumbSelect(e) {
                if (e) e.preventDefault();
                switchToIndex(index, false);
                restartAutoSlide(); // Reset 5-sec timer on user click
            }

            thumb.addEventListener('click', onThumbSelect);
            thumb.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    onThumbSelect(e);
                }
            });
        });
    }

    // Scroll Down / Next Thumbnail Button
    if (thumbsNavBtn) {
        thumbsNavBtn.addEventListener('click', function (e) {
            if (e) e.preventDefault();
            const nextIdx = (currentIndex + 1) % thumbItems.length;
            switchToIndex(nextIdx, false);
            restartAutoSlide();
        });
    }

    // Start auto-slide on page load
    startAutoSlide();

    // Pause auto-rotation when user hovers over the gallery or main image
    if (galleryLayout) {
        galleryLayout.addEventListener('mouseenter', stopAutoSlide);
        galleryLayout.addEventListener('mouseleave', function () {
            // Only resume if lightbox modal is not open
            if (!lightboxModal || !lightboxModal.classList.contains('show')) {
                startAutoSlide();
            }
        });
        galleryLayout.addEventListener('touchstart', stopAutoSlide, { passive: true });
    }

    // Pause auto-rotation when user is not viewing the tab
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            stopAutoSlide();
        } else {
            if (!lightboxModal || !lightboxModal.classList.contains('show')) {
                startAutoSlide();
            }
        }
    });

    // ------------------------------------------------------------------------
    // 2. Lightbox Fullscreen Modal
    // ------------------------------------------------------------------------
    const expandBtn = document.getElementById('showcaseExpandBtn');
    const imageShield = document.getElementById('showcaseImageShield');
    const lightboxClose = document.getElementById('showcaseLightboxClose');

    const openLightbox = function (e) {
        if (e) e.preventDefault();
        stopAutoSlide(); // Stop rotation while inspecting fullscreen

        if (mainImg && lightboxImg) {
            lightboxImg.src = mainImg.src;
        }
        if (lightboxModal) {
            lightboxModal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    };

    const closeLightbox = function () {
        if (lightboxModal) {
            lightboxModal.classList.remove('show');
        }
        document.body.style.overflow = '';
        startAutoSlide(); // Resume rotation after closing lightbox
    };

    if (expandBtn) {
        expandBtn.addEventListener('click', openLightbox);
    }
    if (imageShield) {
        imageShield.addEventListener('click', openLightbox);
    }
    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeLightbox);
    }

    if (lightboxModal) {
        lightboxModal.addEventListener('click', function (e) {
            if (e.target === lightboxModal || e.target.classList.contains('showcase-lightbox-img-wrapper')) {
                closeLightbox();
            }
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && lightboxModal && lightboxModal.classList.contains('show')) {
            closeLightbox();
        }
    });

    // ------------------------------------------------------------------------
    // 3. Tab Navigation
    // ------------------------------------------------------------------------
    const tabBtns = document.querySelectorAll('.showcase-tab-btn');
    const tabPanes = document.querySelectorAll('.showcase-tab-pane');

    function activateTab(tabId) {
        tabBtns.forEach(btn => {
            if (btn.getAttribute('data-tab-target') === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        tabPanes.forEach(pane => {
            if (pane.id === tabId) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
    }

    if (tabBtns.length > 0) {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                const target = this.getAttribute('data-tab-target');
                if (target) {
                    activateTab(target);
                }
            });
        });

        // Check hash in URL (e.g. #tab-reviews)
        if (window.location.hash) {
            const hash = window.location.hash.replace('#', '');
            const targetPane = document.getElementById(hash);
            if (targetPane) {
                activateTab(hash);
            }
        }
    }
});

/**
 * Stepper for Detail Page Quantity Input
 */
function changeShowcaseQty(delta) {
    const input = document.getElementById('showcaseQtyInput');
    if (!input) return;
    let currentVal = parseInt(input.value) || 1;
    let minVal = parseInt(input.getAttribute('min')) || 1;
    let maxVal = parseInt(input.getAttribute('max')) || 999;
    let newVal = currentVal + delta;
    if (newVal >= minVal && newVal <= maxVal) {
        input.value = newVal;
    }
}
