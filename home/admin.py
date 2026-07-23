from django.contrib import admin
from django.db import models
from django.forms import Textarea
from .models import WebsiteSetting, ContactInfo, HeroSlider, OfferBanner, Testimonial, CMSPage, FAQ, InstagramPost, ContactMessage, ContactSubmission, BudgetRange, WhyChooseUs, FabricCuration

class SingletonAdmin(admin.ModelAdmin):
    # Prevents adding new items if one already exists
    def has_add_permission(self, request):
        num_objects = self.model.objects.count()
        if num_objects >= 1:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

class WebsiteSettingAdmin(SingletonAdmin):
    list_display = ['website_name', 'primary_color', 'secondary_color', 'currency', 'tax_percentage', 'shipping_charge', 'free_shipping_limit', 'maintenance_mode']

class ContactInfoAdmin(SingletonAdmin):
    list_display = ['phone', 'email', 'working_hours']
    fields = [
        'phone',
        'email',
        'facebook_url',
        'instagram_url',
        'youtube_url',
        'twitter_url',
        'pinterest_url',
        'whatsapp_number',
        'address',
        'working_hours',
        'google_map_iframe',
    ]
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'style': 'height: 80px; width: 100%; max-width: 600px;'})},
    }

class HeroSliderAdmin(admin.ModelAdmin):
    list_display = ['title', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['title', 'subtitle']

class OfferBannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['title']

class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'role_or_location', 'rating', 'is_active']
    list_filter = ['is_active', 'rating']
    search_fields = ['customer_name', 'comment']

class CMSPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}

class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['question', 'answer']

class InstagramPostAdmin(admin.ModelAdmin):
    list_display = ['id', 'display_order', 'is_active']
    list_filter = ['is_active']

class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at']
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    
    def has_add_permission(self, request):
        return False

class BudgetRangeAdmin(admin.ModelAdmin):
    list_display = ['title', 'min_price', 'max_price', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    search_fields = ['title']

from rangam_saradha_silk.admin import custom_admin_site

custom_admin_site.register(WebsiteSetting, WebsiteSettingAdmin)
custom_admin_site.register(ContactInfo, ContactInfoAdmin)
custom_admin_site.register(HeroSlider, HeroSliderAdmin)
custom_admin_site.register(OfferBanner, OfferBannerAdmin)
custom_admin_site.register(Testimonial, TestimonialAdmin)
custom_admin_site.register(CMSPage, CMSPageAdmin)
custom_admin_site.register(FAQ, FAQAdmin)
custom_admin_site.register(InstagramPost, InstagramPostAdmin)
custom_admin_site.register(ContactMessage, ContactMessageAdmin)
custom_admin_site.register(BudgetRange, BudgetRangeAdmin)

class WhyChooseUsAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'icon_class', 'image', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    search_fields = ['title', 'description']

custom_admin_site.register(WhyChooseUs, WhyChooseUsAdmin)

class FabricCurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'image', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']

custom_admin_site.register(FabricCuration, FabricCurationAdmin)
