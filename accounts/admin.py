from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Address, Wishlist

from rangam_saradha_silk.admin import custom_admin_site

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'phone_number', 'is_verified', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Attributes', {'fields': ('phone_number', 'is_verified', 'otp_code', 'otp_expiry')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Attributes', {'fields': ('phone_number', 'is_verified')}),
    )

class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'phone_number', 'city', 'state', 'pincode', 'address_type', 'is_default']
    list_filter = ['state', 'address_type', 'is_default']
    search_fields = ['full_name', 'city', 'pincode', 'user__username']

class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    search_fields = ['user__username', 'product__name']

custom_admin_site.register(CustomUser, CustomUserAdmin)
custom_admin_site.register(Address, AddressAdmin)
custom_admin_site.register(Wishlist, WishlistAdmin)
