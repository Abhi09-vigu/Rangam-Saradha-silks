/**
 * Manual Product Image Zoom System
 * Features:
 * - NO auto zoom on hover or mouse enter (defaults to 100% scale)
 * - ONLY explicit + and − buttons control zoom level (0.25x steps, 1x to 4x)
 * - White circular buttons (42px x 42px) with black icons & soft shadow
 * - Disabled states when scale = 1x (-) or scale = 4x (+)
 * - Draggable/pannable image when zoomed (> 1x)
 * - NO wheel zoom, NO hover zoom, NO double click zoom
 * - Zero layout shift with GPU-accelerated CSS transforms (translate & scale)
 */
class ProductImageZoom {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        if (!this.container) return;

        this.img = this.container.querySelector('img');
        if (!this.img) return;

        this.options = Object.assign({
            minScale: 1.0,
            maxScale: 4.0,
            zoomStep: 0.25,
            onZoomChange: null
        }, options);

        this.scale = 1.0;
        this.translateX = 0;
        this.translateY = 0;
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.initialTranslateX = 0;
        this.initialTranslateY = 0;

        this.init();
    }

    init() {
        this.container.classList.add('product-zoom-container');
        this.img.classList.add('product-zoom-img');

        this.setupControls();
        this.bindEvents();
        this.observeImageChanges();
    }

    setupControls() {
        let controls = this.container.querySelector('.product-zoom-controls');
        if (!controls) {
            controls = document.createElement('div');
            controls.className = 'product-zoom-controls';
            controls.innerHTML = `
                <button type="button" class="zoom-btn zoom-out-btn" title="Zoom Out (−)" aria-label="Zoom Out" disabled>
                    <i class="bi bi-dash-lg"></i>
                </button>
                <button type="button" class="zoom-btn zoom-in-btn" title="Zoom In (+)" aria-label="Zoom In">
                    <i class="bi bi-plus-lg"></i>
                </button>
            `;
            this.container.appendChild(controls);
        }

        this.zoomOutBtn = controls.querySelector('.zoom-out-btn');
        this.zoomInBtn = controls.querySelector('.zoom-in-btn');

        if (this.zoomInBtn) {
            this.zoomInBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.zoomTo(this.scale + this.options.zoomStep);
            });
        }

        if (this.zoomOutBtn) {
            this.zoomOutBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.zoomTo(this.scale - this.options.zoomStep);
            });
        }

        this.updateButtonsState();
    }

    bindEvents() {
        // Drag / Pan when zoomed (> 1x)
        this.container.addEventListener('mousedown', (e) => this.onMouseDown(e));
        window.addEventListener('mousemove', (e) => this.onWindowMouseMove(e));
        window.addEventListener('mouseup', () => this.onMouseUp());

        // Touch support for drag / pan on mobile when zoomed
        this.container.addEventListener('touchstart', (e) => this.onTouchStart(e), { passive: false });
        this.container.addEventListener('touchmove', (e) => this.onTouchMove(e), { passive: false });
        this.container.addEventListener('touchend', () => this.onTouchEnd());
        this.container.addEventListener('touchcancel', () => this.onTouchEnd());
    }

    observeImageChanges() {
        // Reset zoom state if main image src is changed (e.g. thumbnail click)
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                    this.reset();
                }
            });
        });
        observer.observe(this.img, { attributes: true });
    }

    getMaxOffsets() {
        const rect = this.container.getBoundingClientRect();
        const maxTranslateX = (rect.width * (this.scale - 1)) / 2;
        const maxTranslateY = (rect.height * (this.scale - 1)) / 2;
        return { rect, maxTranslateX, maxTranslateY };
    }

    clampTranslations() {
        const { maxTranslateX, maxTranslateY } = this.getMaxOffsets();
        this.translateX = Math.min(Math.max(this.translateX, -maxTranslateX), maxTranslateX);
        this.translateY = Math.min(Math.max(this.translateY, -maxTranslateY), maxTranslateY);
    }

    updateTransform(animate = true) {
        if (animate) {
            this.container.classList.remove('is-dragging');
        } else {
            this.container.classList.add('is-dragging');
        }

        if (this.scale <= 1.0) {
            this.scale = 1.0;
            this.translateX = 0;
            this.translateY = 0;
            this.container.classList.remove('zoomed');
        } else {
            this.container.classList.add('zoomed');
        }

        this.clampTranslations();
        this.img.style.transform = `translate3d(${this.translateX}px, ${this.translateY}px, 0px) scale(${this.scale})`;
        this.updateButtonsState();

        if (typeof this.options.onZoomChange === 'function') {
            this.options.onZoomChange(this.scale);
        }
    }

    updateButtonsState() {
        if (this.zoomOutBtn) {
            this.zoomOutBtn.disabled = this.scale <= this.options.minScale;
        }
        if (this.zoomInBtn) {
            this.zoomInBtn.disabled = this.scale >= this.options.maxScale;
        }
    }

    onMouseDown(e) {
        if (this.scale <= 1.0 || e.button !== 0) return;
        if (e.target.closest('.product-zoom-controls')) return;

        e.preventDefault();
        this.isDragging = true;
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;
        this.initialTranslateX = this.translateX;
        this.initialTranslateY = this.translateY;

        this.container.classList.add('is-dragging');
    }

    onWindowMouseMove(e) {
        if (!this.isDragging) return;

        const deltaX = e.clientX - this.dragStartX;
        const deltaY = e.clientY - this.dragStartY;

        this.translateX = this.initialTranslateX + deltaX;
        this.translateY = this.initialTranslateY + deltaY;

        this.updateTransform(false);
    }

    onMouseUp() {
        if (this.isDragging) {
            this.isDragging = false;
            this.container.classList.remove('is-dragging');
        }
    }

    onTouchStart(e) {
        if (this.scale > 1.0 && e.touches.length === 1) {
            if (e.target.closest('.product-zoom-controls')) return;
            if (e.cancelable) e.preventDefault();

            this.isDragging = true;
            this.dragStartX = e.touches[0].clientX;
            this.dragStartY = e.touches[0].clientY;
            this.initialTranslateX = this.translateX;
            this.initialTranslateY = this.translateY;
            this.container.classList.add('is-dragging');
        }
    }

    onTouchMove(e) {
        if (this.isDragging && e.touches.length === 1 && this.scale > 1.0) {
            if (e.cancelable) e.preventDefault();

            const deltaX = e.touches[0].clientX - this.dragStartX;
            const deltaY = e.touches[0].clientY - this.dragStartY;

            this.translateX = this.initialTranslateX + deltaX;
            this.translateY = this.initialTranslateY + deltaY;

            this.updateTransform(false);
        }
    }

    onTouchEnd() {
        this.isDragging = false;
        this.container.classList.remove('is-dragging');
    }

    zoomTo(targetScale) {
        const clampedScale = Math.min(Math.max(this.options.minScale, targetScale), this.options.maxScale);
        if (clampedScale === this.scale) return;

        this.scale = clampedScale;
        this.updateTransform(true);
    }

    reset() {
        this.scale = 1.0;
        this.translateX = 0;
        this.translateY = 0;
        this.isDragging = false;
        this.updateTransform(true);
    }

    static initAll(selector = '[data-product-zoom]', options = {}) {
        const containers = document.querySelectorAll(selector);
        return Array.from(containers).map(c => new ProductImageZoom(c, options));
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProductImageZoom;
} else {
    window.ProductImageZoom = ProductImageZoom;
}
