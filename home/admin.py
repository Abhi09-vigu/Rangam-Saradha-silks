from django.contrib import admin
from django.db import models
from django.forms import Textarea
from .models import WebsiteSetting, ContactInfo, HeroSlider, OfferBanner, Testimonial, CMSPage, FAQ, InstagramPost, ContactMessage, ContactSubmission, BudgetRange, WhyChooseUs, FabricCuration, Popup

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
    fieldsets = (
        ('General Website Settings', {
            'fields': ('website_name', 'logo', 'favicon', ('primary_color', 'secondary_color'), 'currency', ('tax_percentage', 'shipping_charge', 'free_shipping_limit'), 'maintenance_mode'),
        }),
        ('Traditional Saree Collections Section (Categories)', {
            'fields': ('category_subtitle', 'category_title', 'category_description', ('category_button_text', 'category_button_url')),
            'description': 'Configure the eyebrow label, main heading, description text, and view-all button for the homepage categories carousel.'
        }),
        ('About Section', {
            'fields': ('about_subtitle', 'about_title', 'about_description', 'about_image', ('about_button_text', 'about_button_url')),
        }),
        ('Bridal Banner Section', {
            'fields': ('bridal_banner_title', 'bridal_banner_subtitle', 'bridal_banner_image', ('bridal_banner_button_text', 'bridal_banner_button_url')),
        }),
        ('Why Choose Us Section', {
            'fields': ('why_choose_subtitle', 'why_choose_title'),
        }),
        ('Fabric Curations Section', {
            'fields': ('fabric_curation_subtitle', 'fabric_curation_title'),
        }),
    )

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
    list_display = ['title', 'subtitle', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['title', 'subtitle', 'description']
    fieldsets = (
        ('Banner Media (Image or Video)', {
            'fields': ('image', 'mobile_image', 'video_file', 'video_url'),
            'description': 'Upload a background image or a looping background video (.mp4/.webm file or URL). If video is provided, it will autoplay seamlessly.'
        }),
        ('Headings & Content', {
            'fields': ('subtitle', 'title', 'description'),
            'description': 'Configure the eyebrow subtitle, main heading (supports line breaks), and supporting description.'
        }),
        ('Action Buttons', {
            'fields': (('button_text', 'button_url'), ('secondary_button_text', 'secondary_button_url')),
            'description': 'Primary CTA (e.g. Explore Collections) and Secondary CTA (e.g. Watch Our Story).'
        }),
        ('Heritage Trust Indicators', {
            'fields': ('heritage_badge_1', 'heritage_badge_2', 'heritage_badge_3'),
            'description': 'Three trust labels displayed at the bottom of the hero.'
        }),
        ('Settings', {
            'fields': ('display_order', 'is_active')
        }),
    )

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

class PopupAdmin(admin.ModelAdmin):
    list_display = ['title', 'popup_type', 'priority', 'is_active', 'start_date', 'end_date', 'created_at']
    list_editable = ['is_active', 'priority']
    list_filter = ['is_active', 'popup_type', 'created_at']
    search_fields = ['title', 'badge_text', 'description', 'coupon_code']
    ordering = ['-priority', '-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'badge_text', 'popup_type', 'description'),
        }),
        ('Media (Image or Video)', {
            'fields': ('image', 'video', 'video_url'),
            'description': 'Upload an image or video to showcase inside the popup modal.',
        }),
        ('Action & Interactions', {
            'fields': ('cta_text', 'cta_link', 'coupon_code', 'whatsapp_number', 'whatsapp_message'),
            'description': 'Configure CTA buttons, discount coupon, or WhatsApp enquiry message.',
        }),
        ('Scheduling, Priority & Visibility', {
            'fields': ('is_active', 'priority', 'start_date', 'end_date', 'show_delay_seconds'),
            'description': 'Higher priority popups take precedence when multiple are active.',
        }),
    )

custom_admin_site.register(Popup, PopupAdmin)
