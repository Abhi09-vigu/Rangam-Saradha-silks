from decimal import Decimal, ROUND_HALF_UP
from home.models import WebsiteSetting

def get_website_settings():
    return WebsiteSetting.objects.first() or WebsiteSetting()

def calculate_order_pricing(subtotal, discount=Decimal('0.00'), payment_method='ONLINE', settings_obj=None):
    """
    Unified, authoritative pricing & eligibility calculation engine for Rangam Saradha Silks.
    Used across Cart, Checkout, Order Creation, Invoices, Customer Receipt & Owner Notification.

    Business Rules:
    1. Every product/order has GST calculated internally based on Website Settings.
    2. Customer views show tax-inclusive totals.
    3. Shipping is FREE for orders above free_shipping_limit.
    4. Cash on Delivery is completely removed. Only 100% secure online payments are accepted.
    """
    if settings_obj is None:
        settings_obj = get_website_settings()

    subtotal = Decimal(str(subtotal))
    discount = Decimal(str(discount or 0))
    if discount > subtotal:
        discount = subtotal

    net_product_total = subtotal - discount

    # 1. Tax / GST Calculation from Website Settings in Admin Panel:
    tax_setting_val = getattr(settings_obj, 'tax_percentage', None)
    if tax_setting_val is not None:
        tax_percent = Decimal(str(tax_setting_val))
    else:
        tax_percent = Decimal('0.00')

    if tax_percent > Decimal('0.00'):
        tax_amount = (net_product_total * tax_percent / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal_with_tax = (subtotal * (Decimal('1.00') + tax_percent / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        tax_amount = Decimal('0.00')
        subtotal_with_tax = subtotal

    taxable_base = net_product_total
    product_total_with_tax = net_product_total + tax_amount
    discount_with_tax = subtotal_with_tax - product_total_with_tax

    # 2. Shipping Calculation
    free_limit = Decimal(str(getattr(settings_obj, 'free_shipping_limit', 1000.00) or 1000.00))
    shipping_charge = Decimal(str(getattr(settings_obj, 'shipping_charge', 0.00) or 0.00))
    shipping = Decimal('0.00') if product_total_with_tax >= free_limit else shipping_charge

    # 3. Order Total (Product Total with GST + Shipping)
    order_amount_before_cod = product_total_with_tax + shipping

    # 4. COD completely removed - only online payments
    is_cod_eligible = False
    cod_is_free = False
    cod_max_limit = Decimal('0.00')
    standard_cod_fee = Decimal('0.00')
    cod_charge = Decimal('0.00')
    effective_payment_method = 'ONLINE' if payment_method in ['COD', None, ''] else payment_method

    # 5. Grand Total (No COD fee added)
    grand_total = order_amount_before_cod

    # 6. Accounting CGST / SGST breakdown (for owner invoice / admin email)
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
