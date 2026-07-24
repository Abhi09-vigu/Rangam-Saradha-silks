from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Address, Wishlist

from rangam_saradha_silk.admin import custom_admin_site

from django.utils.html import format_html

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'phone_number', 'auth_provider', 'avatar_preview', 'is_verified', 'is_staff', 'date_joined', 'last_login']
    list_filter = UserAdmin.list_filter + ('auth_provider', 'is_verified')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Attributes', {'fields': ('phone_number', 'auth_provider', 'google_id', 'firebase_uid', 'profile_picture_url', 'is_verified', 'otp_code', 'otp_expiry')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Attributes', {'fields': ('phone_number', 'auth_provider', 'is_verified')}),
    )

    def avatar_preview(self, obj):
        url = obj.get_avatar_url()
        if url:
            return format_html('<img src="{}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover;" />', url)
        return "-"
    avatar_preview.short_description = "Avatar"

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
