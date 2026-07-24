from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField

class CustomUser(AbstractUser):
    AUTH_PROVIDERS = (
        ('email', 'Email / OTP'),
        ('google', 'Google'),
    )
    phone_number = PhoneNumberField(blank=True, null=True, unique=True)
    is_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    profile_picture_url = models.URLField(max_length=500, blank=True, null=True)
    auth_provider = models.CharField(max_length=20, choices=AUTH_PROVIDERS, default='email')
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    firebase_uid = models.CharField(max_length=255, blank=True, null=True, unique=True)

    def get_avatar_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        if self.profile_picture_url:
            return self.profile_picture_url
        return None

    def __str__(self):
        return self.username

class Address(models.Model):
    ADDRESS_TYPES = (
        ('HOME', 'Home'),
        ('WORK', 'Work/Office'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=150)
    phone_number = PhoneNumberField()
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    landmark = models.CharField(max_length=100, blank=True, null=True)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='HOME')
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Addresses"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set other user addresses default to False
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.pincode}"

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
