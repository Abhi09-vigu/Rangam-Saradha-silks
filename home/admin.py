from django import forms
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

class WebsiteSettingAdminForm(forms.ModelForm):
    class Meta:
        model = WebsiteSetting
        fields = '__all__'
        widgets = {
            'priority_sku_prefixes': forms.TextInput(attrs={
                'placeholder': 'e.g. RSS-GB, KJM-SUB',
                'style': 'max-width: 500px; width: 100%;',
            }),
        }

class WebsiteSettingAdmin(SingletonAdmin):
    form = WebsiteSettingAdminForm
    list_display = ['website_name', 'priority_sku_prefixes', 'hero_display_mode', 'launch_mode_active', 'launch_datetime', 'maintenance_mode', 'gst_number', 'tax_percentage', 'call_booking_fee', 'cod_charge', 'cod_max_limit', 'shipping_charge', 'free_shipping_limit']
    fieldsets = (
        ('🌟 TEMP POPUP: Mandatory Full-Screen Launch Overlay', {
            'fields': ('launch_mode_active', 'launch_datetime', 'launch_title', 'launch_tagline_1', 'launch_tagline_2'),
            'description': 'Control the mandatory full-screen launch overlay. Turn OFF "TEMP POPUP Active" anytime to open the website early without touching code. While ON, normal visitors see the full-screen countdown overlay until the launch date/time is reached. Staff/Superusers can always access and test the website normally.',
        }),
        ('Homepage Top Banner Display (Hero Slider vs Offer Banner)', {
            'fields': ('hero_display_mode',),
            'description': 'Choose whether to show the Hero Slider or the Offer Banner at the top of the homepage. Select "Automatic" (shows Hero Slider if active slides exist, otherwise automatically shows Offer Banner), "Hero Slider Only", or "Offer Banner Only". Only one will be displayed at a time, never both.',
        }),
        ('🏷️ Product Display Priority (SKU Prefixes)', {
            'fields': ('priority_sku_prefixes',),
            'description': 'Control the product display order on the shop and catalog listing pages. Enter SKU prefixes separated by commas (e.g. RSS-GB, KJM-SUB). Products matching these prefixes will appear first on the shop page in this exact order, followed by all remaining products.',
        }),
        ('General Website Settings', {
            'fields': ('website_name', 'gst_number', 'logo', 'favicon', ('primary_color', 'secondary_color'), 'currency', ('tax_percentage', 'shipping_charge', 'free_shipping_limit'), ('cod_charge', 'cod_max_limit', 'call_booking_fee'), 'maintenance_mode'),
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
        ('👑 Section 3: Featured Card 1 (Left)', {
            'fields': (
                'collection_card_1_image',
                'collection_card_1_tag',
                'collection_card_1_title',
                'collection_card_1_desc',
                ('collection_card_1_button_text', 'collection_card_1_button_url'),
            ),
            'description': 'Configure the image, category tag, title name, description, and button link URL for Card 1 (Left: e.g. Kanchipuram Silks).',
        }),
        ('👑 Section 3: Featured Card 2 (Center)', {
            'fields': (
                'collection_card_2_image',
                'collection_card_2_tag',
                'collection_card_2_title',
                'collection_card_2_desc',
                ('collection_card_2_button_text', 'collection_card_2_button_url'),
            ),
            'description': 'Configure the image, category tag, title name, description, and button link URL for Card 2 (Center: e.g. Banarasi Brocades).',
        }),
        ('👑 Section 3: Featured Card 3 (Right)', {
            'fields': (
                'collection_card_3_image',
                'collection_card_3_tag',
                'collection_card_3_title',
                'collection_card_3_desc',
                ('collection_card_3_button_text', 'collection_card_3_button_url'),
            ),
            'description': 'Configure the image, category tag, title name, description, and button link URL for Card 3 (Right: e.g. Bridal Masterpieces).',
        }),
        ('🖼️ Other Homepage Editorial Section Images', {
            'fields': (
                'bridal_spotlight_image',
                'artisan_weaving_image',
                ('mosaic_hero_image', 'mosaic_festive_image', 'mosaic_handloom_image'),
                'brand_story_image',
            ),
            'description': 'Upload custom images for the other homepage editorial sections anytime. If an image is left blank, the curated default image will be displayed automatically.',
        }),
        ('Why Choose Us Section', {
            'fields': ('why_choose_subtitle', 'why_choose_title'),
        }),
        ('Fabric Curations Section', {
            'fields': ('fabric_curation_subtitle', 'fabric_curation_title'),
        }),
    )

class ContactInfoAdmin(SingletonAdmin):
    list_display = ['page_title', 'phone', 'email', 'working_hours']
    fieldsets = (
        ('🌸 1. Top Header Banner', {
            'fields': ('page_title', 'page_subtitle', 'header_bg_image'),
            'description': 'Configure the main page title, subtitle, and optional header background texture.',
        }),
        ('💬 2. Help & Inquiry Section (Top Left)', {
            'fields': ('help_eyebrow', 'help_title', 'help_description'),
            'description': 'Configure the eyebrow text, main heading, and supporting description on the left.',
        }),
        ('📍 3. Card 1: Visit Our Store', {
            'fields': ('store_card_title', 'address', ('store_btn_text', 'store_btn_url')),
            'description': 'Physical store address and Get Directions button link.',
        }),
        ('📞 4. Card 2: Call Us', {
            'fields': ('call_card_title', 'phone', 'phone_hours', ('call_btn_text', 'call_btn_url')),
            'description': 'Store telephone number, availability hours, and direct call button.',
        }),
        ('✉️ 5. Card 3: Email Us', {
            'fields': ('email_card_title', 'email', ('email_btn_text', 'email_btn_url')),
            'description': 'Official customer email address and mailto button.',
        }),
        ('⏰ 6. Card 4: Working Hours', {
            'fields': ('hours_card_title', 'working_hours', 'working_hours_secondary'),
            'description': 'Business operational hours for weekdays and Sundays/weekends.',
        }),
        ('📝 7. Message Form (Top Right)', {
            'fields': ('form_title', 'form_subtitle', 'form_button_text', 'form_subjects'),
            'description': 'Form heading, subtitle, submit button label, and dropdown subjects (one subject per line).',
        }),
        ('✨ 8. Middle Promotional Saree Banner', {
            'fields': (
                'banner_title',
                'banner_description',
                ('banner_button_text', 'banner_button_url'),
                'banner_image',
                ('feature_1_title', 'feature_1_icon'),
                ('feature_2_title', 'feature_2_icon'),
                ('feature_3_title', 'feature_3_icon'),
                ('feature_4_title', 'feature_4_icon'),
            ),
            'description': 'Luxury promotional banner with button and 4 highlighted brand features (icons use Bootstrap Icon class names like bi-gift, bi-flower1, bi-heart, bi-headset).',
        }),
        ('🗺️ 9. Store Location & Interactive Google Map (Bottom)', {
            'fields': (
                'location_eyebrow',
                'location_title',
                'location_description',
                ('location_button_text', 'location_button_url'),
                'google_map_iframe',
            ),
            'description': 'Bottom location section heading, description, directions button, and responsive Google Map iframe.',
        }),
        ('🌐 10. Social Media & Direct WhatsApp', {
            'fields': ('whatsapp_number', 'instagram_url', 'facebook_url', 'youtube_url', 'twitter_url', 'pinterest_url'),
            'description': 'Store social media channels and WhatsApp click-to-chat configuration.',
        }),
    )
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'style': 'height: 80px; width: 100%; max-width: 600px;'})},
    }

class HeroSliderAdmin(admin.ModelAdmin):
    list_display = ['title', 'subtitle', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['title', 'subtitle', 'description']
    fieldsets = (
        ('Banner Media (Image or Video)', {
            'fields': ('image', 'tablet_image', 'mobile_image', 'video_file', 'video_url'),
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
    fieldsets = (
        ('Banner Details', {
            'fields': ('title', 'link', 'display_order', 'is_active')
        }),
        ('Banner Media', {
            'fields': ('image', 'tablet_image', 'mobile_image'),
            'description': 'Upload the desktop banner image, and optionally tablet-optimized (iPad / medium screen) and mobile-optimized (phone) images.'
        }),
    )

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
    list_display = ['name', 'email', 'phone_number', 'subject', 'created_at']
    readonly_fields = ['name', 'email', 'phone_number', 'subject', 'message', 'created_at']
    search_fields = ['name', 'email', 'phone_number', 'subject', 'message']
    
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
