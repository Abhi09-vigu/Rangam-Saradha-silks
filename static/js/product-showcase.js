/**
 * Rangam Saradha Silks - Product Showcase Interactive Controller
 * Handles gallery thumbnails, lightbox preview, interactive tabs, and quantity stepper
 */

document.addEventListener('DOMContentLoaded', function () {
    // ------------------------------------------------------------------------
    // 1. Gallery Thumbnail Switching
    // ------------------------------------------------------------------------
    const mainImg = document.getElementById('showcaseMainImg');
    const thumbItems = document.querySelectorAll('.showcase-thumb-item');
    const thumbsList = document.querySelector('.showcase-thumbs-list');
    const thumbsNavBtn = document.getElementById('showcaseThumbsNavBtn');
    const lightboxImg = document.getElementById('showcaseLightboxImg');

    if (thumbItems.length > 0 && mainImg) {
        thumbItems.forEach((thumb, index) => {
            thumb.addEventListener('click', function () {
                const fullSrc = this.getAttribute('data-full-img');
                if (!fullSrc) return;

                // Update active state
                thumbItems.forEach(t => t.classList.remove('active'));
                this.classList.add('active');

                // Smooth fade transition
                mainImg.style.opacity = '0.4';
                setTimeout(() => {
                    mainImg.src = fullSrc;
                    if (lightboxImg) lightboxImg.src = fullSrc;
                    mainImg.style.opacity = '1';
                }, 120);
            });
        });
    }

    // Scroll Down / Next Thumbnail Button
    if (thumbsNavBtn && thumbsList) {
        thumbsNavBtn.addEventListener('click', function () {
            const activeThumb = document.querySelector('.showcase-thumb-item.active');
            if (activeThumb && activeThumb.nextElementSibling) {
                activeThumb.nextElementSibling.click();
                activeThumb.nextElementSibling.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else if (thumbItems.length > 0) {
                // Wrap to first
                thumbItems[0].click();
                thumbsList.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                thumbsList.scrollBy({ top: 100, behavior: 'smooth' });
            }
        });
    }

    // ------------------------------------------------------------------------
    // 2. Lightbox Fullscreen Modal
    // ------------------------------------------------------------------------
    const expandBtn = document.getElementById('showcaseExpandBtn');
    const imageShield = document.getElementById('showcaseImageShield');
    const lightboxModal = document.getElementById('showcaseLightboxModal');
    const lightboxClose = document.getElementById('showcaseLightboxClose');

    const openLightbox = function (e) {
        if (e) e.preventDefault();
        if (mainImg && lightboxImg) {
            lightboxImg.src = mainImg.src;
        }
        if (lightboxModal) {
            lightboxModal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    };

    if (expandBtn) {
        expandBtn.addEventListener('click', openLightbox);
    }
    if (imageShield) {
        imageShield.addEventListener('click', openLightbox);
    }

        const closeLightbox = function () {
            lightboxModal.classList.remove('show');
            document.body.style.overflow = '';
        };

        if (lightboxClose) {
            lightboxClose.addEventListener('click', closeLightbox);
        }

        lightboxModal.addEventListener('click', function (e) {
            if (e.target === lightboxModal || e.target.classList.contains('showcase-lightbox-img-wrapper')) {
                closeLightbox();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && lightboxModal.classList.contains('show')) {
                closeLightbox();
            }
        });
    }

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
