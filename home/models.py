from django.db import models
from django.utils.text import slugify

class WebsiteSetting(models.Model):
    website_name = models.CharField(max_length=100, default="Rangam Saradha Silk Sarees")
    logo = models.ImageField(upload_to='settings/', blank=True, null=True)
    favicon = models.ImageField(upload_to='settings/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#AF0446", help_text="HEX Color code (e.g. #AF0446)")
    secondary_color = models.CharField(max_length=7, default="#AE6F21", help_text="HEX Color code (e.g. #AE6F21)")
    currency = models.CharField(max_length=10, default="₹")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Tax percentage (e.g., 5.00 for 5% GST)")
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_shipping_limit = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    maintenance_mode = models.BooleanField(default=False)

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
    bridal_banner_button_url = models.CharField(max_length=200, default="/shop/?collection=bridal", help_text="URL the button links to.")

    # Dynamic Why Choose Us Headers
    why_choose_title = models.CharField(max_length=100, default="Why Choose Us", help_text="Main heading for the Why Choose Us section.")
    why_choose_subtitle = models.CharField(max_length=150, default="THE RANGAM SARADHA PROMISE", help_text="Subtitle above the Why Choose Us heading.")

    # Dynamic Fabric Curations Headers
    fabric_curation_title = models.CharField(max_length=100, default="Fabric Curations", help_text="Main heading for the Fabric Curations section.")
    fabric_curation_subtitle = models.CharField(max_length=150, default="SHOP BY MATERIAL", help_text="Subtitle above the Fabric Curations heading.")

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
    phone = models.CharField(max_length=20, default="+91 98765 43210")
    email = models.EmailField(default="contact@rangamsaradhasilk.com")
    address = models.TextField(default="123 Silk Street, Kanchipuram, Tamil Nadu, India")
    google_map_iframe = models.TextField(blank=True, null=True, help_text="Paste the full iframe embed code from Google Maps")
    working_hours = models.CharField(max_length=100, default="Mon - Sat: 9:00 AM - 8:00 PM")
    
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
        verbose_name = "Contact Info"
        verbose_name_plural = "Contact Info"

    def save(self, *args, **kwargs):
        if not self.pk and ContactInfo.objects.exists():
            return
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return "Contact & Social Media Information"

class HeroSlider(models.Model):
    image = models.ImageField(upload_to='slider/')
    mobile_image = models.ImageField(upload_to='slider_mobile/', blank=True, null=True)
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    button_text = models.CharField(max_length=50, default="Shop Now")
    button_url = models.CharField(max_length=255, default="/shop/")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title

class OfferBanner(models.Model):
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='offers/')
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
