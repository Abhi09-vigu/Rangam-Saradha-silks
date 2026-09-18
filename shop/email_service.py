import logging
import threading
from decimal import Decimal, ROUND_HALF_UP
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from home.models import WebsiteSetting

logger = logging.getLogger(__name__)

def send_email_async(msg):
    """
    Background worker thread to dispatch emails asynchronously.
    Catches all exceptions to guarantee checkout/saving is never blocked.
    """
    try:
        msg.send(fail_silently=False)
        logger.info("Asynchronous email dispatched successfully.")
    except Exception as e:
        logger.error(f"Failed to dispatch email asynchronously: {e}", exc_info=True)

def send_order_confirmation_email(order):
    """
    Dispatches a branded order confirmation receipt to the customer's email.
    """
    if not order.email:
        logger.warning(f"Skipping order confirmation email for #{order.order_number} - no email address.")
        return False

    site_settings = WebsiteSetting.objects.first()
    context = {
        'order': order,
        'items': order.items.all(),
        'site_settings': site_settings,
        'site_url': getattr(settings, 'SITE_URL', 'https://rangamsaradhasilks.com'),
    }
    
    subject = f"Thank you for your order! #{order.order_number} - Rangam Saradha Silks"
    
    try:
        html_content = render_to_string('shop/emails/order_confirmation.html', context)
        text_content = strip_tags(html_content)
        
        from_email = settings.DEFAULT_FROM_EMAIL or 'Rangam Saradha Silks <rangamsaradhasilks@gmail.com>'
        to_email = [order.email]
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        
        # Dispatch in background thread
        threading.Thread(target=send_email_async, args=(msg,)).start()
        return True
    except Exception as e:
        logger.error(f"Error preparing order confirmation email for #{order.order_number}: {e}", exc_info=True)
        return False

def send_order_status_update_email(order, original_status):
    """
    Dispatches a status update alert to the customer when the order progress state changes.
    """
    if not order.email:
        logger.warning(f"Skipping status update email for #{order.order_number} - no email address.")
        return False

    site_settings = WebsiteSetting.objects.first()
    
    # Map status keywords to user friendly names & messages
    status_messages = {
        'PENDING': 'Your order is currently pending review.',
        'CONFIRMED': 'Good news! Your order has been confirmed and is being processed.',
        'PACKED': 'Your beautiful saree has been packed carefully and is ready for dispatch.',
        'SHIPPED': 'Exciting! Your order has been handed over to our courier partners and is shipped.',
        'OUT_FOR_DELIVERY': 'Your parcel is out for delivery today and will reach you shortly!',
        'DELIVERED': 'Delivered! We hope you love your handwoven pure silk saree.',
        'CANCELLED': 'Your order has been cancelled as requested or due to processing issues.',
        'RETURNED': 'We have received your returned item and are processing it.',
        'REFUNDED': 'Your refund has been issued successfully.',
    }
    
    status_message = status_messages.get(order.order_status, f"Your order status has been updated to {order.get_order_status_display()}.")
    
    context = {
        'order': order,
        'items': order.items.all(),
        'site_settings': site_settings,
        'status_display': order.get_order_status_display(),
        'status_message': status_message,
        'original_status_display': dict(order.STATUS_CHOICES).get(original_status, original_status),
        'site_url': getattr(settings, 'SITE_URL', 'https://rangamsaradhasilks.com'),
    }
    
    subject = f"Order #{order.order_number} Status Update: {order.get_order_status_display()} - Rangam Saradha Silks"
    
    try:
        html_content = render_to_string('shop/emails/order_status_update.html', context)
        text_content = strip_tags(html_content)
        
        from_email = settings.DEFAULT_FROM_EMAIL or 'Rangam Saradha Silks <rangamsaradhasilks@gmail.com>'
        to_email = [order.email]
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        
        # Dispatch in background thread
        threading.Thread(target=send_email_async, args=(msg,)).start()
        return True
    except Exception as e:
        logger.error(f"Error preparing status update email for #{order.order_number}: {e}", exc_info=True)
        return False

def send_owner_order_notification_email(order):
    """
    Dispatches a comprehensive accounting & order alert email to the store owner/admin.
    Sent on every order to rangamsaradhasilks@gmail.com with complete 5% GST breakdown,
    GSTIN, itemised SKU breakdown, COD charges, and customer info.
    """
    admin_recipient = "rangamsaradhasilks@gmail.com"
    site_settings = WebsiteSetting.objects.first()
    
    # Calculate 5% GST accounting split
    total_gst_amount = Decimal(str(order.tax_amount or '0.00'))
    cgst_amount = (total_gst_amount / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sgst_amount = total_gst_amount - cgst_amount
    
    subtotal = Decimal(str(order.subtotal or '0.00'))
    discount = Decimal(str(order.discount_amount or '0.00'))
    taxable_value = subtotal - discount - total_gst_amount
    
    gst_number = site_settings.gst_number if site_settings and site_settings.gst_number else "33AAAAA0000A1Z5"
    currency = site_settings.currency if site_settings and site_settings.currency else "₹"
    
    context = {
        'order': order,
        'items': order.items.all(),
        'site_settings': site_settings,
        'gst_number': gst_number,
        'currency': currency,
        'taxable_value': taxable_value,
        'total_gst_amount': total_gst_amount,
        'cgst_amount': cgst_amount,
        'sgst_amount': sgst_amount,
        'site_url': getattr(settings, 'SITE_URL', 'https://rangamsaradhasilks.com'),
    }
    
    subject = f"New Order Received: #{order.order_number} ({currency}{order.grand_total}) - Rangam Saradha Silks"
    
    try:
        html_content = render_to_string('shop/emails/admin_order_notification.html', context)
        text_content = strip_tags(html_content)
        
        from_email = settings.DEFAULT_FROM_EMAIL or 'Rangam Saradha Silks <rangamsaradhasilks@gmail.com>'
        to_email = [admin_recipient]
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        
        # Dispatch in background thread
        threading.Thread(target=send_email_async, args=(msg,)).start()
        return True
    except Exception as e:
        logger.error(f"Error preparing admin order notification email for #{order.order_number}: {e}", exc_info=True)
        return False

