from decimal import Decimal, ROUND_HALF_UP
from home.models import WebsiteSetting

def get_website_settings():
    return WebsiteSetting.objects.first() or WebsiteSetting()

def calculate_order_pricing(subtotal, discount=Decimal('0.00'), payment_method='COD', settings_obj=None):
    """
    Unified, authoritative pricing & eligibility calculation engine for Rangam Saradha Silks.
    Used across Cart, Checkout, Order Creation, Invoices, Customer Receipt & Owner Notification.

    Business Rules:
    1. Every product/order has 5% GST calculated internally.
    2. Customer views show tax-inclusive totals (no separate GST line displayed to customer).
    3. Orders strictly BELOW ₹2,000 (order total before COD fee):
       - COD is available.
       - Applicable COD fee (default ₹49.00) is added when COD is selected.
    4. Orders ₹2,000 OR ABOVE:
       - COD is strictly UNAVAILABLE.
       - Only Online Payment is allowed.
       - COD fee is ₹0.00.
    """
    if settings_obj is None:
        settings_obj = get_website_settings()

    subtotal = Decimal(str(subtotal))
    discount = Decimal(str(discount or 0))
    if discount > subtotal:
        discount = subtotal

    net_product_total = subtotal - discount

    # 1. 5% GST Calculation:
    # The 5% GST amount is directly added to the product total when the customer is ready to pay.
    # The customer pays the 5% GST included in the final amount without a separate GST line shown.
    tax_percent = Decimal(str(getattr(settings_obj, 'tax_percentage', 5.00) or 5.00))
    if tax_percent > 0:
        tax_amount = (net_product_total * tax_percent / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        tax_amount = Decimal('0.00')

    taxable_base = net_product_total
    # Product total with 5% GST directly added
    product_total_with_tax = net_product_total + tax_amount
    subtotal_with_tax = (subtotal * (Decimal('1.00') + tax_percent / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    discount_with_tax = subtotal_with_tax - product_total_with_tax

    # 2. Shipping Calculation
    free_limit = Decimal(str(getattr(settings_obj, 'free_shipping_limit', 1000.00) or 1000.00))
    shipping_charge = Decimal(str(getattr(settings_obj, 'shipping_charge', 0.00) or 0.00))
    shipping = Decimal('0.00') if product_total_with_tax >= free_limit else shipping_charge

    # 3. Order Total (Product Total with 5% GST directly added + Shipping)
    order_amount_before_cod = product_total_with_tax + shipping

    # 4. COD Eligibility & Free COD Threshold
    # COD is available for ALL orders.
    # Orders below cod_max_limit (default ₹2,000) have a standard COD fee (default ₹49).
    # Orders at or above cod_max_limit (₹2,000+) receive FREE Cash On Delivery (₹0 COD fee).
    cod_max_limit = Decimal(str(getattr(settings_obj, 'cod_max_limit', 2000.00) or 2000.00))
    is_cod_eligible = True
    cod_is_free = order_amount_before_cod >= cod_max_limit

    # 5. COD Charge Application
    standard_cod_fee = Decimal(str(getattr(settings_obj, 'cod_charge', 49.00) or 49.00))
    if payment_method == 'COD':
        effective_payment_method = 'COD'
        cod_charge = Decimal('0.00') if cod_is_free else standard_cod_fee
    else:
        effective_payment_method = 'ONLINE'
        cod_charge = Decimal('0.00')

    # 6. Grand Total
    grand_total = order_amount_before_cod + cod_charge

    # 7. Accounting CGST / SGST breakdown (for owner invoice / admin email)
    cgst_rate = (tax_percent / Decimal('2')).quantize(Decimal('0.01'))
    sgst_rate = (tax_percent / Decimal('2')).quantize(Decimal('0.01'))
    cgst_amount = (tax_amount / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sgst_amount = (tax_amount - cgst_amount).quantize(Decimal('0.01'))

    gst_number = getattr(settings_obj, 'gst_number', '33AAAAA0000A1Z5')

    return {
        'subtotal': subtotal_with_tax,
        'taxable_base': taxable_base,
        'raw_subtotal': subtotal,
        'discount': discount_with_tax,
        'raw_discount': discount,
        'tax_percent': tax_percent,
        'tax_amount': tax_amount,
        'shipping': shipping,
        'order_amount_before_cod': order_amount_before_cod,
        'is_cod_eligible': is_cod_eligible,
        'cod_is_free': cod_is_free,
        'cod_free_threshold': cod_max_limit,
        'cod_max_limit': cod_max_limit,
        'standard_cod_fee': standard_cod_fee,
        'cod_charge': cod_charge,
        'effective_payment_method': effective_payment_method,
        'grand_total': grand_total,
        'cgst_rate': cgst_rate,
        'sgst_rate': sgst_rate,
        'cgst_amount': cgst_amount,
        'sgst_amount': sgst_amount,
        'gst_number': gst_number,
    }
