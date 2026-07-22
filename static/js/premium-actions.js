/**
 * Rangam Saradha Silk - Premium Product Actions Script
 * Handles: Wishlist (AJAX & Local Storage), Quick View Modal, Toast Notifications
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize guest wishlist on load
    initGuestWishlist();

    // Bind event listeners
    bindWishlistEvents();
    bindQuickViewEvents();
    bindModalCloseEvents();
});

/* ==========================================================================
   Toast Notification System
   ========================================================================== */
function showPremiumToast(message, type = 'success') {
    const container = document.querySelector('.premium-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `premium-toast show toast-${type}`;

    let icon = 'bi-check-circle-fill text-success';
    if (type === 'error') icon = 'bi-exclamation-triangle-fill text-danger';
    if (type === 'info') icon = 'bi-info-circle-fill text-primary';

    toast.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi ${icon} fs-5 me-3"></i>
            <div class="toast-body fw-medium text-dark">${message}</div>
            <button type="button" class="btn-close ms-auto shadow-none" style="font-size: 0.65rem;" aria-label="Close"></button>
        </div>
    `;

    container.appendChild(toast);

    // Close button event
    toast.querySelector('.btn-close').addEventListener('click', () => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    });

    // Auto close
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }
    }, 4000);
}

/* ==========================================================================
   Wishlist Toggling Logic
   ========================================================================== */
function getGuestWishlist() {
    try {
        return JSON.parse(localStorage.getItem('guest_wishlist')) || [];
    } catch (e) {
        return [];
    }
}

function initGuestWishlist() {
    if (IS_USER_AUTHENTICATED) return; // DB wishlist handles on server side

    const guestList = getGuestWishlist();
    if (guestList.length === 0) return;

    guestList.forEach(productId => {
        updateWishlistIcons(productId, true);
    });
}

function updateWishlistIcons(productId, isWishlisted) {
    const btns = document.querySelectorAll(`.wishlist-btn[data-product-id="${productId}"]`);
    btns.forEach(btn => {
        const icon = btn.querySelector('i');
        const textSpan = btn.querySelector('span'); // Modal wishlist button may have text

        if (isWishlisted) {
            if (icon) {
                icon.className = 'bi bi-heart-fill active';
            }
            if (textSpan) {
                textSpan.textContent = 'In Wishlist';
            }
            btn.classList.add('active');
        } else {
            if (icon) {
                icon.className = 'bi bi-heart';
            }
            if (textSpan) {
                textSpan.textContent = 'Add to Wishlist';
            }
            btn.classList.remove('active');
        }
    });
}

function toggleWishlistAction(productId) {
    if (IS_USER_AUTHENTICATED) {
        // Authenticated user: AJAX toggle database wishlist
        fetch(`/accounts/wishlist/toggle/${productId}/`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.added !== undefined) {
                updateWishlistIcons(productId, data.added);
                showPremiumToast(data.message, 'success');
            } else {
                showPremiumToast("Error updating wishlist.", "error");
            }
        })
        .catch(error => {
            console.error('Error toggling wishlist:', error);
            showPremiumToast("Could not update wishlist. Please try again.", "error");
        });
    } else {
        // Guest user: localStorage toggle
        let guestList = getGuestWishlist();
        const index = guestList.indexOf(parseInt(productId));
        let added = false;
        let message = '';

        if (index > -1) {
            guestList.splice(index, 1);
            message = 'Product removed from your Wishlist.';
        } else {
            guestList.push(parseInt(productId));
            added = true;
            message = 'Product added to Wishlist. Log in to save it permanently!';
        }

        localStorage.setItem('guest_wishlist', JSON.stringify(guestList));
        updateWishlistIcons(productId, added);
        showPremiumToast(message, added ? 'success' : 'info');
    }
}

function bindWishlistEvents() {
    // Use event delegation to handle clicks on wishlist buttons
    document.addEventListener('click', (e) => {
        const wishlistBtn = e.target.closest('.wishlist-btn');
        if (wishlistBtn) {
            e.preventDefault();
            e.stopPropagation();
            const productId = wishlistBtn.getAttribute('data-product-id');
            if (productId) {
                toggleWishlistAction(productId);
            }
        }
    });
}

/* ==========================================================================
   Quick View Modal Logic
   ========================================================================== */
function bindQuickViewEvents() {
    document.addEventListener('click', (e) => {
        const quickViewBtn = e.target.closest('.quickview-btn');
        if (quickViewBtn) {
            e.preventDefault();
            e.stopPropagation();
            const productId = quickViewBtn.getAttribute('data-product-id');
            if (productId) {
                openQuickView(productId);
            }
        }
    });
}

function openQuickView(productId) {
    const modal = document.getElementById('premiumQuickViewModal');
    const contentContainer = modal.querySelector('.quickview-content');

    // Show loading state
    contentContainer.innerHTML = `
        <div class="d-flex justify-content-center align-items-center py-5 w-100">
            <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;" role="status">
                <span class="visually-hidden">Loading product details...</span>
            </div>
        </div>
    `;
    modal.classList.add('show');
    document.body.classList.add('overflow-hidden');

    // Fetch product details
    fetch(`/shop/product/${productId}/quick-view/`, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response not ok');
        return response.json();
    })
    .then(product => {
        renderQuickViewModal(product, contentContainer);
    })
    .catch(error => {
        console.error('Error loading quick view:', error);
        contentContainer.innerHTML = `
            <div class="text-center py-5 w-100 px-3">
                <i class="bi bi-exclamation-circle text-danger fs-1 mb-3"></i>
                <h4 class="font-heading">Unable to load details</h4>
                <p class="text-muted">Something went wrong while fetching product information.</p>
                <button type="button" class="btn btn-primary rounded-pill px-4 mt-2 quickview-close-btn-retry">Close</button>
            </div>
        `;
        contentContainer.querySelector('.quickview-close-btn-retry').addEventListener('click', closeQuickView);
    });
}

function renderQuickViewModal(product, container) {
    // Generate image galleries
    let mainImageHtml = `
        <img id="qv-main-img" src="${product.images[0]}" alt="${product.name}" class="w-100 h-100 object-fit-cover">
    `;

    let thumbHtml = '';
    if (product.images.length > 1) {
        thumbHtml = '<div class="quickview-thumbnails d-flex gap-2 mt-2 overflow-x-auto pb-1">';
        product.images.forEach((imgUrl, idx) => {
            thumbHtml += `
                <div class="qv-thumb-wrapper ${idx === 0 ? 'active' : ''}" data-img-url="${imgUrl}" style="width: 60px; aspect-ratio: 3/4; overflow: hidden; border-radius: 4px; cursor: pointer; border: 2px solid ${idx === 0 ? 'var(--primary)' : 'transparent'}; transition: all 0.2s;">
                    <img src="${imgUrl}" alt="${product.name}" class="w-100 h-100 object-fit-cover">
                </div>
            `;
        });
        thumbHtml += '</div>';
    }

    // Discount status / pricing markup
    let priceHtml = `
        <span class="fs-4 fw-bold text-primary mr-2">${product.current_price.toFixed(2)}</span>
    `;
    if (product.original_price) {
        priceHtml = `
            <span class="fs-4 fw-bold text-primary me-2">₹${product.current_price.toFixed(2)}</span>
            <span class="text-muted text-decoration-line-through me-2 fs-6">₹${product.original_price.toFixed(2)}</span>
            <span class="badge bg-success-subtle text-success fs-8">Save ${product.discount_percentage}%</span>
        `;
    } else {
        priceHtml = `
            <span class="fs-4 fw-bold text-primary">₹${product.current_price.toFixed(2)}</span>
        `;
    }

    // Stock badges
    let stockBadgeHtml = '';
    if (product.stock === 0) {
        stockBadgeHtml = `<span class="badge bg-danger text-white px-2 py-1 fs-7">Out of Stock</span>`;
    } else if (product.stock <= 5) {
        stockBadgeHtml = `<span class="badge bg-warning text-dark px-2 py-1 fs-7">Only ${product.stock} Left</span>`;
    } else {
        stockBadgeHtml = `<span class="badge bg-success text-white px-2 py-1 fs-7">In Stock</span>`;
    }

    // Highlights list
    let highlightsHtml = '';
    if (product.highlights && product.highlights.length > 0) {
        highlightsHtml = `
            <div class="quickview-highlights-section mt-3">
                <h6 class="fw-bold fs-7 text-uppercase text-muted mb-2" style="letter-spacing: 0.05em;">Product Features</h6>
                <ul class="list-unstyled mb-0 row g-1">
                    ${product.highlights.map(hl => `<li class="col-6 fs-7 text-dark"><i class="bi bi-check2-circle text-primary me-2"></i>${hl}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    // Modal Wishlist state check
    let isWishlistedInLocal = false;
    if (!IS_USER_AUTHENTICATED) {
        const guestList = getGuestWishlist();
        isWishlistedInLocal = guestList.includes(parseInt(product.id));
    }
    const isWishlistActive = IS_USER_AUTHENTICATED ? product.in_wishlist : isWishlistedInLocal;

    // Rendered html
    container.innerHTML = `
        <div class="row g-4 m-0 w-100">
            <!-- Left: Images -->
            <div class="col-md-6 p-0 pr-md-3">
                <div class="quickview-image-container position-relative bg-light" style="aspect-ratio: 3/4; overflow: hidden; border-radius: 12px;">
                    ${mainImageHtml}
                </div>
                ${thumbHtml}
            </div>
            
            <!-- Right: Details -->
            <div class="col-md-6 p-0 ps-md-3 d-flex flex-column justify-content-between">
                <div>
                    <span class="fs-8 text-uppercase text-muted fw-semibold tracking-wider">${product.category}</span>
                    <h2 class="font-heading fs-3 text-dark mt-1 mb-2">${product.name}</h2>
                    
                    <div class="d-flex align-items-center gap-3 mb-3">
                        <div class="price-section">${priceHtml}</div>
                        <div class="stock-section">${stockBadgeHtml}</div>
                    </div>
                    
                    <div class="text-muted fs-7 mb-3 qv-desc-wrap" style="line-height: 1.6;">
                        ${product.short_description}
                    </div>
                    
                    ${highlightsHtml}
                </div>
                
                <div>
                    <!-- Quantity & Add/Buy Form -->
                    <form action="${product.add_to_cart_url}" method="POST" class="mt-4">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${CSRF_TOKEN}">
                        
                        <div class="d-flex align-items-center gap-3 mb-3">
                            <span class="fs-7 fw-semibold text-muted">Quantity:</span>
                            <div class="input-group input-group-sm" style="width: 110px; border-radius: 20px; overflow: hidden; border: 1px solid var(--border-color);">
                                <button class="btn btn-outline-secondary border-0 qv-qty-btn qv-qty-minus" type="button" style="background: #f8f9fa;">-</button>
                                <input type="number" name="quantity" class="form-control border-0 text-center qv-qty-input fs-7" value="1" min="1" max="${product.stock}" style="box-shadow: none; font-weight: 600;">
                                <button class="btn btn-outline-secondary border-0 qv-qty-btn qv-qty-plus" type="button" style="background: #f8f9fa;">+</button>
                            </div>
                        </div>
                        
                        <div class="d-flex gap-2">
                            <button type="submit" class="btn btn-primary flex-grow-1 py-2 rounded-pill font-heading text-uppercase text-white fs-7" ${product.stock === 0 ? 'disabled' : ''}>
                                <i class="bi bi-bag-plus me-1"></i> Add To Cart
                            </button>
                            <button type="submit" name="buy_now" value="true" class="btn btn-gold flex-grow-1 py-2 rounded-pill font-heading text-uppercase text-white fs-7" ${product.stock === 0 ? 'disabled' : ''}>
                                Buy Now
                            </button>
                        </div>
                    </form>
                    
                    <div class="d-flex gap-2 align-items-center mt-3">
                        <!-- Wishlist Toggle -->
                        <button type="button" class="btn btn-outline-dark wishlist-btn flex-grow-1 py-2 rounded-pill fs-7" data-product-id="${product.id}">
                            <i class="bi ${isWishlistActive ? 'bi-heart-fill active' : 'bi-heart'} me-2"></i>
                            <span>${isWishlistActive ? 'In Wishlist' : 'Add to Wishlist'}</span>
                        </button>
                    </div>

                    <!-- View Details Link -->
                    <a href="${product.detail_url}" class="btn btn-link text-muted mt-2 w-100 text-center fs-7 text-decoration-none hover-primary">
                        View Full Details <i class="bi bi-arrow-right ms-1"></i>
                    </a>
                </div>
            </div>
        </div>
    `;

    // Bind Image Thumbnails Click Event
    const thumbWrappers = container.querySelectorAll('.qv-thumb-wrapper');
    const mainImg = container.querySelector('#qv-main-img');
    thumbWrappers.forEach(thumb => {
        thumb.addEventListener('click', () => {
            // Set image
            const imgUrl = thumb.getAttribute('data-img-url');
            if (mainImg) mainImg.src = imgUrl;

            // Highlight thumbnail border
            thumbWrappers.forEach(w => {
                w.style.borderColor = 'transparent';
                w.classList.remove('active');
            });
            thumb.style.borderColor = 'var(--primary)';
            thumb.classList.add('active');
        });
    });

    // Bind Quantity Input Events
    const minusBtn = container.querySelector('.qv-qty-minus');
    const plusBtn = container.querySelector('.qv-qty-plus');
    const qtyInput = container.querySelector('.qv-qty-input');
    
    if (qtyInput) {
        minusBtn.addEventListener('click', () => {
            let current = parseInt(qtyInput.value) || 1;
            if (current > 1) {
                qtyInput.value = current - 1;
            }
        });
        plusBtn.addEventListener('click', () => {
            let current = parseInt(qtyInput.value) || 1;
            let max = parseInt(qtyInput.getAttribute('max')) || 99;
            if (current < max) {
                qtyInput.value = current + 1;
            }
        });
    }
}

function closeQuickView() {
    const modal = document.getElementById('premiumQuickViewModal');
    if (modal) {
        modal.classList.remove('show');
    }
    document.body.classList.remove('overflow-hidden');
}

function bindModalCloseEvents() {
    const modal = document.getElementById('premiumQuickViewModal');
    if (!modal) return;

    // Click close icon
    const closeBtn = modal.querySelector('.quickview-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeQuickView);
    }

    // Click overlay
    const overlay = modal.querySelector('.quickview-overlay');
    if (overlay) {
        overlay.addEventListener('click', closeQuickView);
    }

    // ESC key press
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('show')) {
            closeQuickView();
        }
    });
}
