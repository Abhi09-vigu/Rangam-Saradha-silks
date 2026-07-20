from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Order
from .email_service import send_order_confirmation_email, send_order_status_update_email

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
    Triggers after saving. If the order is newly created, it sends the confirmation receipt.
    Otherwise, if the status has changed, it sends an update email notification.
    """
    if created:
        send_order_confirmation_email(instance)
    else:
        original_status = getattr(instance, '_original_order_status', None)
        if original_status and original_status != instance.order_status:
            send_order_status_update_email(instance, original_status)
