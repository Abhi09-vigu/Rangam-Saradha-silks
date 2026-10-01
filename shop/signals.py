from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Order
from .email_service import (
    send_order_confirmation_email,
    send_order_status_update_email,
    send_owner_order_notification_email,
)

@receiver(pre_save, sender=Order)
def order_pre_save(sender, instance, **kwargs):
    """
    Checks the initial status of the order before saving to detect if it has changed.
    """
    if instance.pk:
        try:
            original = Order.objects.get(pk=instance.pk)
            instance._original_order_status = original.order_status
        except Order.DoesNotExist:
            instance._original_order_status = None
    else:
        instance._original_order_status = None

@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """
    Triggers after saving.
    For Razorpay/Online orders, confirmation email is sent once payment is verified and confirmed.
    Otherwise, if the status has changed, it sends an update email notification.
    """
    if created:
        # Don't send confirmation email for online payments until payment is verified
        if instance.payment_method in ['RAZORPAY', 'ONLINE'] and instance.payment_status != 'PAID':
            return
        send_order_confirmation_email(instance)
    else:
        original_status = getattr(instance, '_original_order_status', None)
        # Check if an online order just got confirmed upon payment verification
        if original_status == 'PENDING' and instance.order_status == 'CONFIRMED' and instance.payment_status == 'PAID':
            send_order_confirmation_email(instance)
        elif original_status and original_status != instance.order_status:
            send_order_status_update_email(instance, original_status)
