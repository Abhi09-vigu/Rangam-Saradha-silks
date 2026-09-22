/**
 * Real-time bidirectional calculation between Price, Discount percentage, and Offer price in Django Admin.
 */
document.addEventListener('DOMContentLoaded', function () {
    const priceInput = document.getElementById('id_price');
    const discountInput = document.getElementById('id_discount_percentage');
    const offerPriceInput = document.getElementById('id_offer_price');

    if (!priceInput || !discountInput || !offerPriceInput) {
        return;
    }

    let isUpdating = false;

    // Calculate offer price when discount percentage or price changes
    function calculateOfferPrice() {
        if (isUpdating) return;
        isUpdating = true;
        try {
            const price = parseFloat(priceInput.value);
            const discount = parseFloat(discountInput.value);

            if (!isNaN(price) && price > 0) {
                if (!isNaN(discount) && discount >= 0 && discount <= 100) {
                    const offer = price - (price * (discount / 100));
                    offerPriceInput.value = (Math.round(offer * 100) / 100).toFixed(2);
                } else if (isNaN(discount) || discountInput.value.trim() === '') {
                    offerPriceInput.value = price.toFixed(2);
                }
            }
        } finally {
            isUpdating = false;
        }
    }

    // Calculate discount percentage when offer price changes directly
    function calculateDiscountPercentage() {
        if (isUpdating) return;
        isUpdating = true;
        try {
            const price = parseFloat(priceInput.value);
            const offerPrice = parseFloat(offerPriceInput.value);

            if (!isNaN(price) && price > 0) {
                if (!isNaN(offerPrice) && offerPrice >= 0) {
                    if (offerPrice < price) {
                        const discount = ((price - offerPrice) / price) * 100;
                        discountInput.value = Math.round(discount);
                    } else {
                        // Offer price is equal to or greater than base price -> 0% discount
                        discountInput.value = 0;
                    }
                } else if (offerPriceInput.value.trim() === '') {
                    discountInput.value = 0;
                }
            }
        } finally {
            isUpdating = false;
        }
    }

    // Event listeners for real-time input & change
    discountInput.addEventListener('input', calculateOfferPrice);
    discountInput.addEventListener('change', calculateOfferPrice);

    offerPriceInput.addEventListener('input', calculateDiscountPercentage);
    offerPriceInput.addEventListener('change', calculateDiscountPercentage);

    priceInput.addEventListener('input', function () {
        const discountVal = discountInput.value.trim();
        const offerVal = offerPriceInput.value.trim();

        if (discountVal !== '' && parseFloat(discountVal) > 0) {
            calculateOfferPrice();
        } else if (offerVal !== '') {
            calculateDiscountPercentage();
        }
    });
    priceInput.addEventListener('change', function () {
        const discountVal = discountInput.value.trim();
        const offerVal = offerPriceInput.value.trim();

        if (discountVal !== '' && parseFloat(discountVal) > 0) {
            calculateOfferPrice();
        } else if (offerVal !== '') {
            calculateDiscountPercentage();
        }
    });
});
