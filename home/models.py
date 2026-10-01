from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.db import models
from django.utils.text import slugify

DEFAULT_LAUNCH_DT = datetime(2026, 9, 25, 10, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

class WebsiteSetting(models.Model):
    website_name = models.CharField(max_length=100, default="Rangam Saradha Silk Sarees")
    logo = models.ImageField(upload_to='settings/', blank=True, null=True)
    favicon = models.ImageField(upload_to='settings/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#AF0446", help_text="HEX Color code (e.g. #AF0446)")
    secondary_color = models.CharField(max_length=7, default="#AE6F21", help_text="HEX Color code (e.g. #AE6F21)")
    currency = models.CharField(max_length=10, default="₹")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax percentage in Website Settings (e.g., 5.00 for 5% GST, or 0.00 for no tax). Applied to all products when set.")
    gst_number = models.CharField(max_length=30, default="33AAAAA0000A1Z5", blank=True, help_text="Business GSTIN for invoices and tax compliance")
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_shipping_limit = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    call_booking_fee = models.DecimalField(max_digits=8, decimal_places=2, default=50.00, help_text="Fee required to book a live video saree consultation (default: ₹50.00)")
    maintenance_mode = models.BooleanField(default=False)

    # Product Display Priority (SKU Prefixes)
    priority_sku_prefixes = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Priority SKU Prefixes",
        help_text="Enter any comma-separated SKU prefixes (e.g. RSS-SA, KJM-SUB, RSS-GB, or any new SKU code you create). Products matching any prefix you enter will automatically appear first on the shop page and homepage in this exact priority order."
    )

    # Hero Slider vs Offer Banner Top Display Mode
    hero_display_mode = models.CharField(
        max_length=20,
        choices=[
            ('AUTO', 'Automatic (Hero Slider if active, else Offer Banner)'),
            ('HERO_SLIDER', 'Hero Slider Only'),
            ('OFFER_BANNER', 'Offer Banner Only'),
        ],
        default='AUTO',
        verbose_name="Homepage Top Banner Display",
        help_text="Choose whether to show the Hero Slider or the Offer Banner at the top of the homepage. In 'Automatic' mode, the Hero Slider is shown if active slides exist; if hero sliders are removed/deactivated, it automatically shows the Offer Banner instead. Either one will be displayed, never both simultaneously."
    )

    # Mandatory TEMP POPUP / Launch Lock Settings
    launch_mode_active = models.BooleanField(
        default=True,
        verbose_name="TEMP POPUP Active (Enable/Disable)",
        help_text="Turn OFF anytime to immediately open the site early without touching code. When ON, normal visitors see the mandatory full-screen launch overlay until the launch date/time arrives."
    )
    launch_datetime = models.DateTimeField(
        default=DEFAULT_LAUNCH_DT,
        verbose_name="Grand Opening Date & Time (Asia/Kolkata)",
        help_text="Target launch date & time in Asia/Kolkata (e.g. 25 September 2026 at 10:30 AM). The overlay automatically disappears when this time arrives."
    )
    launch_title = models.CharField(
        max_length=150,
        default="Grand Opening Soon",
        verbose_name="Popup Headline",
        help_text="Headline displayed on the mandatory launch overlay."
    )
    launch_tagline_1 = models.CharField(
        max_length=200,
        default="Something beautiful is about to begin.",
        verbose_name="Popup Subtitle",
        help_text="Subtitle displayed right below the brand title."
    )
    launch_tagline_2 = models.CharField(
        max_length=200,
        default="Tradition in Every Weave",
        verbose_name="Popup Tagline",
        help_text="Tagline displayed below the countdown timer."
    )

    @property
    def is_temp_popup_active(self):
        if not self.launch_mode_active:
            return False
        from django.utils import timezone
        now = timezone.now()
        target = self.launch_datetime or DEFAULT_LAUNCH_DT
        return now < target

    @property
    def cod_charge(self):
        return Decimal('0.00')

    @property
    def cod_max_limit(self):
        return Decimal('0.00')

    @property
    def cod_free_threshold(self):
        return Decimal('0.00')

    def get_priority_sku_prefixes(self):
        """
        Returns an ordered list of clean, non-empty, deduplicated SKU prefixes.
        Example: 'RSS-GB, KJM-SUB' -> ['RSS-GB', 'KJM-SUB']
        """
        if not self.priority_sku_prefixes:
            return []
        prefixes = []
        for p in self.priority_sku_prefixes.split(','):
            cleaned = p.strip()
            if cleaned and cleaned not in prefixes:
                prefixes.append(cleaned)
        return prefixes

    # Dynamic About Section
    about_title = models.CharField(max_length=150, default="About Rangam Saradha Silk Sarees", help_text="Main heading for the homepage About section.")
    about_subtitle = models.CharField(max_length=100, default="LEGACY OF ELEGANCE", help_text="Small subtitle label above the main heading.")
    about_description = models.TextField(
        default="At Rangam Saradha Silk Sarees, each saree tells a story of artistic heritage, intricate handwork, and modern designs tailored for the contemporary Indian woman. From royal Kanchipurams to exquisite designer silks, we offer unmatched purity and premium luxury.",
        help_text="Detailed description of the brand/about section."
    )
    about_image = models.ImageField(upload_to='about/', blank=True, null=True, help_text="Portrait image for the homepage About section.")
    about_button_text = models.CharField(max_length=50, default="Read Our Full Story", help_text="Text to display on the action button.")
    about_button_url = models.CharField(max_length=200, default="/page/about-us/", help_text="URL / page link the button redirects to.")

    # Dynamic Bridal Banner Section
    bridal_banner_title = models.CharField(max_length=150, default="Bridal Collection", help_text="Title for the homepage bridal banner.")
    bridal_banner_subtitle = models.TextField(default="Exquisite handcrafted Kanchipuram bridal silk sarees designed for your special day.", help_text="Subtitle or description text.")
    bridal_banner_image = models.ImageField(upload_to='bridal/', blank=True, null=True, help_text="Background image for the bridal banner.")
    bridal_banner_button_text = models.CharField(max_length=50, default="Shop Wedding Collection", help_text="Text on the banner button.")
    bridal_banner_button_url = models.CharField(max_length=200, default="/shop/?category=bridal-collection", help_text="URL the button links to.")

    # Dynamic Why Choose Us Headers
    why_choose_title = models.CharField(max_length=100, default="Why Choose Us", help_text="Main heading for the Why Choose Us section.")
    why_choose_subtitle = models.CharField(max_length=150, default="THE RANGAM SARADHA PROMISE", help_text="Subtitle above the Why Choose Us heading.")

    # Dynamic Fabric Curations Headers
    fabric_curation_title = models.CharField(max_length=100, default="Fabric Curations", help_text="Main heading for the Fabric Curations section.")
    fabric_curation_subtitle = models.CharField(max_length=150, default="SHOP BY MATERIAL", help_text="Subtitle above the Fabric Curations heading.")

    # Dynamic Categories Section Headers
    category_title = models.CharField(max_length=150, default="Traditional Saree Collections", help_text="Main heading for the Categories section.")
    category_subtitle = models.CharField(max_length=100, default="SHOP BY CATEGORY", help_text="Label above Categories heading.")
    category_description = models.CharField(max_length=255, default="Explore timeless weaves crafted for every occasion.", help_text="Description text below Categories heading.")
    category_button_text = models.CharField(max_length=50, default="View All Categories", help_text="Text for the Categories CTA button.")
    category_button_url = models.CharField(max_length=200, default="/shop/", help_text="URL / link for the Categories CTA button.")

    # Dynamic Editorial Homepage Images & Content (Editable from Admin)
    # 1. Section 3: Featured Collection Cards (3 Cards)
    # Card 1
    collection_card_1_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Card 1 Image", help_text="Upload custom image for Card 1. Defaults to curated static image if left blank.")
    collection_card_1_tag = models.CharField(max_length=100, default="ROYAL HERITAGE", verbose_name="Card 1 Tag / Subtitle")
    collection_card_1_title = models.CharField(max_length=150, default="Kanchipuram Silks", verbose_name="Card 1 Title / Name")
    collection_card_1_desc = models.TextField(default="Woven with authentic gold zari and sacred temple architecture borders for grand celebrations.", verbose_name="Card 1 Description")
    collection_card_1_button_text = models.CharField(max_length=50, default="Explore Collection", verbose_name="Card 1 Button Text")
    collection_card_1_button_url = models.CharField(max_length=255, default="/shop/category/kanchipuram-sarees/", verbose_name="Card 1 Button Link (URL)", help_text="Page URL or category link (e.g. /shop/category/kanchipuram-sarees/)")

    # Card 2
    collection_card_2_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Card 2 Image", help_text="Upload custom image for Card 2. Defaults to curated static image if left blank.")
    collection_card_2_tag = models.CharField(max_length=100, default="MUGHAL SPLENDOR", verbose_name="Card 2 Tag / Subtitle")
    collection_card_2_title = models.CharField(max_length=150, default="Banarasi Brocades", verbose_name="Card 2 Title / Name")
    collection_card_2_desc = models.TextField(default="Intricate floral jaal, meenakari embellishments, and cascading silk pallus for regal occasions.", verbose_name="Card 2 Description")
    collection_card_2_button_text = models.CharField(max_length=50, default="Explore Collection", verbose_name="Card 2 Button Text")
    collection_card_2_button_url = models.CharField(max_length=255, default="/shop/category/banarasi-sarees/", verbose_name="Card 2 Button Link (URL)", help_text="Page URL or category link (e.g. /shop/category/banarasi-sarees/)")

    # Card 3
    collection_card_3_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Card 3 Image", help_text="Upload custom image for Card 3. Defaults to curated static image if left blank.")
    collection_card_3_tag = models.CharField(max_length=100, default="MASTER WEAVES", verbose_name="Card 3 Tag / Subtitle")
    collection_card_3_title = models.CharField(max_length=150, default="Bridal Masterpieces", verbose_name="Card 3 Title / Name")
    collection_card_3_desc = models.TextField(default="Our hallmark bridal drapes infused with enduring warmth, double-warp silk, and artisanal soul.", verbose_name="Card 3 Description")
    collection_card_3_button_text = models.CharField(max_length=50, default="Explore Collection", verbose_name="Card 3 Button Text")
    collection_card_3_button_url = models.CharField(max_length=255, default="/shop/category/bridal-collection/", verbose_name="Card 3 Button Link (URL)", help_text="Page URL or category link (e.g. /shop/category/bridal-collection/)")

    # 2. Section 5: The Bridal Repertory Spotlight
    bridal_spotlight_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Bridal Repertory Spotlight Image", help_text="Upload custom image for 'The Bridal Repertory - A Symphony of Pure Silk & Golden Zari' section.")

    # 3. Section 6: Ancient Weaving Art (Master Artisan)
    artisan_weaving_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Ancient Weaving Art Artisan Image", help_text="Upload custom image for 'Ancient Weaving Art - Crafted by Hands That Breathe Tradition' section.")

    # 4. Section 8: Latest Weaves & Editorial Inspiration (Mosaic Grid)
    mosaic_hero_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Mosaic Large Focal Image (Heirloom Zari Artistry)", help_text="Upload custom image for the large left frame in 'Latest Weaves & Editorial Inspiration'.")
    mosaic_festive_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Mosaic Top Right Image (Festive Drapery)", help_text="Upload custom image for the top right frame 'Festive Drapery Collections'.")
    mosaic_handloom_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Mosaic Bottom Right Image (Dharmavaram Hallmarks)", help_text="Upload custom image for the bottom right frame 'Dharmavaram Hallmarks'.")

    # 5. Section 9: Brand Story (Tradition Woven With Elegance)
    brand_story_image = models.ImageField(upload_to='editorial/', blank=True, null=True, verbose_name="Brand Story Heritage Image", help_text="Upload custom image for the Brand Story ('Tradition Woven With Elegance / 40+ Years Legacy') section.")

    class Meta:
        verbose_name = "Website Setting"
        verbose_name_plural = "Website Settings"

    def save(self, *args, **kwargs):
        # Force the primary key to always be 1 to guarantee a singleton record
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.website_name

class ContactInfo(models.Model):
    # Header Section
    page_title = models.CharField(max_length=150, default="Contact Us", help_text="Main heading on the contact page")
    page_subtitle = models.CharField(max_length=255, default="Connect with Rangam Saradha Silks", help_text="Subtitle under main heading")
    header_bg_image = models.ImageField(upload_to='contact/', blank=True, null=True, help_text="Optional custom background/texture for the header")

    # Help Section (Left Top)
    help_eyebrow = models.CharField(max_length=150, default="WE'D LOVE TO HEAR FROM YOU", help_text="Small gold eyebrow label")
    help_title = models.CharField(max_length=150, default="We're Here to Help", help_text="Heading for the left contact section")
    help_description = models.TextField(
        default="Have a question about our pure silk sarees, custom orders, or shipping times? Drop us a line or visit our flagship store. Our team will be happy to assist you.",
        help_text="Introductory text explaining how customers can get in touch"
    )

    # 1. Visit Our Store Card
    store_card_title = models.CharField(max_length=100, default="Visit Our Store")
    address = models.TextField(default="Door No-28-747-1, Rajendra Nagar, Dharmavaram, Sri Sathya Sai District, Andhra Pradesh - 515671")
    store_btn_text = models.CharField(max_length=50, default="Get Directions")
    store_btn_url = models.CharField(max_length=300, default="https://maps.google.com/?q=Rangam+Saradha+Silks+Dharmavaram", blank=True, help_text="Map URL or direction link")

    # 2. Call Us Card
    call_card_title = models.CharField(max_length=100, default="Call Us")
    phone = models.CharField(max_length=30, default="+91 91002 88963")
    phone_hours = models.CharField(max_length=100, default="Mon - Sat: 9:00 AM - 7:00 PM", help_text="Phone availability hours")
    call_btn_text = models.CharField(max_length=50, default="Call Now")
    call_btn_url = models.CharField(max_length=100, default="tel:+919100288963", blank=True)

    # 3. Email Us Card
    email_card_title = models.CharField(max_length=100, default="Email Us")
    email = models.EmailField(default="rangamsaradhasilks@gmail.com")
    email_btn_text = models.CharField(max_length=50, default="Send Email")
    email_btn_url = models.CharField(max_length=150, default="mailto:rangamsaradhasilks@gmail.com", blank=True)

    # 4. Working Hours Card
    hours_card_title = models.CharField(max_length=100, default="Working Hours")
    working_hours = models.CharField(max_length=100, default="Mon - Sat: 9:00 AM - 7:00 PM")
    working_hours_secondary = models.CharField(max_length=100, default="Sun: 9:00 AM - 12:00 PM", blank=True)

    # Send Us a Message Form Card (Right Top)
    form_title = models.CharField(max_length=100, default="Send Us a Message")
    form_subtitle = models.CharField(max_length=200, default="We'll get back to you as soon as possible.")
    form_button_text = models.CharField(max_length=50, default="Send Message")
    form_subjects = models.TextField(
        default="Inquiry about Pure Silk Sarees\nCustom Bridal Order\nOrder Status & Shipping\nStore Visit & Video Call\nBulk & Wholesale Inquiry\nOther Inquiries",
        help_text="Subject options for the form dropdown (one per line)"
    )

    # Middle Promotional Saree Banner
    banner_title = models.CharField(max_length=150, default="Looking for the Perfect Saree?")
    banner_description = models.TextField(
        default="From traditional silk sarees to elegant wedding collections, we're here to help you find the perfect saree for every occasion."
    )
    banner_button_text = models.CharField(max_length=60, default="Explore Our Collection")
    banner_button_url = models.CharField(max_length=255, default="/shop/")
    banner_image = models.ImageField(upload_to='contact/', blank=True, null=True, help_text="Custom background image for the middle saree banner")
    
    feature_1_title = models.CharField(max_length=100, default="Wedding Collections")
    feature_1_icon = models.CharField(max_length=50, default="bi-gift", help_text="Bootstrap icon class")
    feature_2_title = models.CharField(max_length=100, default="Traditional Silk Sarees")
    feature_2_icon = models.CharField(max_length=50, default="bi-flower1", help_text="Bootstrap icon class")
    feature_3_title = models.CharField(max_length=100, default="Custom Orders")
    feature_3_icon = models.CharField(max_length=50, default="bi-heart", help_text="Bootstrap icon class")
    feature_4_title = models.CharField(max_length=100, default="Customer Support")
    feature_4_icon = models.CharField(max_length=50, default="bi-headset", help_text="Bootstrap icon class")

    # Bottom Store Location Section
    location_eyebrow = models.CharField(max_length=100, default="OUR LOCATION")
    location_title = models.CharField(max_length=150, default="Visit Rangam Saradha Silks")
    location_description = models.TextField(default="Experience our exclusive collection in person at our Dharmavaram store.")
    location_button_text = models.CharField(max_length=50, default="Get Directions")
    location_button_url = models.CharField(max_length=300, default="https://maps.google.com/?q=Rangam+Saradha+Silks+Dharmavaram")
    google_map_iframe = models.TextField(blank=True, null=True, help_text="Paste the full iframe embed code from Google Maps")

    # Social Media
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    pinterest_url = models.URLField(blank=True, null=True)
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="WhatsApp number with country code, without spaces or symbols (e.g. 919876543210 or 9876543210)",
    )

    def get_subject_list(self):
        if not self.form_subjects:
            return ["Inquiry about Pure Silk Sarees", "Custom Bridal Order", "Order Status & Shipping", "Other Inquiries"]
        return [line.strip() for line in self.form_subjects.splitlines() if line.strip()]

    @property
    def whatsapp_url(self):
        if self.whatsapp_number:
            cleaned = "".join(char for char in str(self.whatsapp_number) if char.isdigit())
            if len(cleaned) == 10:
                cleaned = "91" + cleaned
            if cleaned:
                return f"https://wa.me/{cleaned}?text=Hello%20Rangam%20Saradha%20Silks"
        return None

    @property
    def safe_google_map_iframe(self):
        if not self.google_map_iframe:
            return ""
        from .utils import sanitize_and_format_google_map
        try:
            return sanitize_and_format_google_map(self.google_map_iframe)
        except Exception:
            return ""

    def clean(self):
        super().clean()
        if self.google_map_iframe:
            from .utils import sanitize_and_format_google_map
            self.google_map_iframe = sanitize_and_format_google_map(self.google_map_iframe)

    class Meta:
        verbose_name = "Contact Info & Page Settings"
        verbose_name_plural = "Contact Info & Page Settings"

    def save(self, *args, **kwargs):
        if not self.pk and ContactInfo.objects.exists():
            return
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return "Contact & Page Information"

class HeroSlider(models.Model):
    image = models.ImageField(upload_to='slider/', help_text="Background image (used if no video is provided or as poster)")
    tablet_image = models.ImageField(upload_to='slider_tablet/', blank=True, null=True, help_text="Optional tablet-optimized image (768px - 991px)")
    mobile_image = models.ImageField(upload_to='slider_mobile/', blank=True, null=True, help_text="Optional mobile-optimized image (up to 767px)")
    video_file = models.FileField(upload_to='slider_videos/', blank=True, null=True, help_text="Optional background video file (.mp4, .webm)")
    video_url = models.URLField(blank=True, null=True, help_text="Optional background video URL (e.g. Cloudinary or direct MP4 link)")
    title = models.CharField(max_length=150, default="Woven by Hand.\nMade to Treasure.", help_text="Main heading (can use line breaks)")
    subtitle = models.CharField(max_length=255, blank=True, null=True, default="HANDWOVEN HERITAGE", help_text="Eyebrow text above headline")
    description = models.TextField(blank=True, null=True, default="Pure Silks. Timeless Traditions. For Your Most Precious Moments.", help_text="Supporting description below headline")
    button_text = models.CharField(max_length=50, default="Explore Collections")
    button_url = models.CharField(max_length=255, default="/shop/")
    secondary_button_text = models.CharField(max_length=50, default="Watch Our Story", blank=True, null=True)
    secondary_button_url = models.CharField(max_length=255, blank=True, null=True, help_text="Link for secondary button (leave blank to open Story Video modal)")
    heritage_badge_1 = models.CharField(max_length=60, default="Authentic Handloom", blank=True)
    heritage_badge_2 = models.CharField(max_length=60, default="Pure Silk Guaranteed", blank=True)
    heritage_badge_3 = models.CharField(max_length=60, default="A Legacy of Tradition", blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    @property
    def has_video(self):
        if self.video_file:
            return True
        if self.video_url:
            return True
        if self.image:
            name = str(self.image.name).lower()
            return name.endswith('.mp4') or name.endswith('.webm') or '/video/upload/' in name
        return False

    @property
    def get_video_src(self):
        if self.video_file:
            return self.video_file.url
        if self.video_url:
            return self.video_url
        if self.image:
            name = str(self.image.name).lower()
            if name.endswith('.mp4') or name.endswith('.webm') or '/video/upload/' in name:
                return self.image.url
        return ""

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title

class OfferBanner(models.Model):
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='offers/', help_text="Desktop banner image (wide screens)")
    tablet_image = models.ImageField(upload_to='offers/tablet/', blank=True, null=True, help_text="Optional tablet-optimized image (shown on iPads & tablet screens: 768px - 991px). If not uploaded, desktop image will be used.")
    mobile_image = models.ImageField(upload_to='offers/mobile/', blank=True, null=True, help_text="Optional mobile-optimized image (shown on phones & mobile screens: up to 767px). If not uploaded, desktop image will be used.")
    link = models.CharField(max_length=255, default="/shop/")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title

class Testimonial(models.Model):
    customer_name = models.CharField(max_length=100)
    role_or_location = models.CharField(max_length=100, default="Customer")
    comment = models.TextField()
    rating = models.IntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    image = models.ImageField(upload_to='testimonials/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.customer_name

class CMSPage(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField(help_text="HTML or Markdown text describing page body")
    
    # SEO
    meta_title = models.CharField(max_length=150, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    meta_keywords = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('home:cms_page', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.question

class InstagramPost(models.Model):
    image = models.ImageField(upload_to='instagram/')
    link = models.URLField(default="https://instagram.com/")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"Instagram Post {self.id}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True, null=True, default='')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"


ContactSubmission = ContactMessage


class BudgetRange(models.Model):
    title = models.CharField(max_length=100, help_text="e.g. Under ₹2000, ₹2000 - ₹4000")
    min_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Minimum price filter value. Leave blank for no minimum.")
    max_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Maximum price filter value. Leave blank for no maximum.")
    display_order = models.IntegerField(default=0, help_text="Order in which it will be displayed.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "Budget Range"
        verbose_name_plural = "Budget Ranges"

    def __str__(self):
        return self.title

class WhyChooseUs(models.Model):
    title = models.CharField(max_length=100, help_text="e.g. Free Shipping")
    description = models.CharField(max_length=150, blank=True, null=True, help_text="e.g. On orders over ₹1000")
    icon_class = models.CharField(max_length=255, default="bi-truck", blank=True, help_text="Bootstrap Icon class (e.g. bi-truck) OR PNG file path/URL")
    image = models.ImageField(upload_to='why_choose_us/', blank=True, null=True, help_text="Upload custom PNG/SVG icon image")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "Why Choose Us Item"
        verbose_name_plural = "Why Choose Us Items"

    def __str__(self):
        return self.title


class FabricCuration(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. Banarasi, Kanchipattu, Organza")
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='fabric_curations/', blank=True, null=True, help_text="Upload card background image for this fabric curation")
    description = models.CharField(max_length=200, blank=True, null=True, help_text="Optional short description or subtitle")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Fabric Curation"
        verbose_name_plural = "Fabric Curations"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Popup(models.Model):
    POPUP_TYPE_CHOICES = (
        ('OFFER', 'Special Offer 🎁'),
        ('CALL_BOOKING', 'Book a Call for Saree Selection 📞'),
        ('VIDEO', 'Saree Video 🎥'),
        ('WHATSAPP', 'WhatsApp / Enquiry 💬'),
        ('COLLECTION', 'Collection Promotion 🛍️'),
    )

    title = models.CharField(max_length=200, help_text="Headline for the popup modal")
    badge_text = models.CharField(max_length=100, blank=True, null=True, help_text="Top badge label (e.g. 🎁 SPECIAL OFFER, 📞 VIP CONSULTATION)")
    popup_type = models.CharField(max_length=30, choices=POPUP_TYPE_CHOICES, default='OFFER', help_text="Select the interactive behavior and layout for this popup")
    description = models.TextField(blank=True, null=True, help_text="Detailed message, terms, or promotional offer details")
    
    # Media
    image = models.ImageField(upload_to='popups/', blank=True, null=True, help_text="Visual image banner for the popup")
    video = models.FileField(upload_to='popups/videos/', blank=True, null=True, help_text="Upload optional MP4/WebM video")
    video_url = models.URLField(blank=True, null=True, help_text="Optional external or Cloudinary video URL")
    
    # Call to Actions & Interactions
    cta_text = models.CharField(max_length=60, default="Explore Now", help_text="Button label (e.g. Shop Collection, Book My Call)")
    cta_link = models.CharField(max_length=255, default="/shop/", help_text="Destination URL when visitor clicks the CTA button")
    coupon_code = models.CharField(max_length=50, blank=True, null=True, help_text="Optional discount code to display with 1-click copy")
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, help_text="Custom WhatsApp number (leave blank to use store default)")
    whatsapp_message = models.CharField(max_length=255, blank=True, default="Hello Rangam Saradha Silks, I would like to know more about your authentic handloom sarees.", help_text="Pre-filled WhatsApp message")

    # Scheduling & Controls
    is_active = models.BooleanField(default=True, help_text="Enable or disable this popup from appearing on the website")
    priority = models.IntegerField(default=0, help_text="Higher number = higher priority. If multiple active popups exist, only the highest priority popup is shown.")
    start_date = models.DateTimeField(blank=True, null=True, help_text="Popup starts appearing after this date/time (leave blank for immediately)")
    end_date = models.DateTimeField(blank=True, null=True, help_text="Popup stops appearing after this date/time (leave blank for no expiration)")
    show_delay_seconds = models.PositiveIntegerField(default=2, help_text="Delay in seconds after page load before displaying (1-2s recommended)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = "Popup"
        verbose_name_plural = "Popups"

    def __str__(self):
        return f"[{self.get_popup_type_display()}] {self.title} (Priority: {self.priority})"

    @property
    def is_currently_eligible(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

