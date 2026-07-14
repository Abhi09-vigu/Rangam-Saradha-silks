from django.db import models
from django.utils.text import slugify

class WebsiteSetting(models.Model):
    website_name = models.CharField(max_length=100, default="Rangam Saradha Silk Sarees")
    logo = models.ImageField(upload_to='settings/', blank=True, null=True)
    favicon = models.ImageField(upload_to='settings/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#AF0446", help_text="HEX Color code (e.g. #AF0446)")
    secondary_color = models.CharField(max_length=7, default="#AE6F21", help_text="HEX Color code (e.g. #AE6F21)")
    currency = models.CharField(max_length=10, default="₹")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax percentage (e.g., 5.00 for 5% GST)")
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_shipping_limit = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Website Setting"
        verbose_name_plural = "Website Settings"

    def save(self, *args, **kwargs):
        # Override to ensure only one record exists
        if not self.pk and WebsiteSetting.objects.exists():
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.website_name

class ContactInfo(models.Model):
    phone = models.CharField(max_length=20, default="+91 98765 43210")
    email = models.EmailField(default="contact@rangamsaradhasilk.com")
    address = models.TextField(default="123 Silk Street, Kanchipuram, Tamil Nadu, India")
    google_map_iframe = models.TextField(blank=True, null=True, help_text="Paste full <iframe> embed tag from Google Maps")
    working_hours = models.CharField(max_length=100, default="Mon - Sat: 9:00 AM - 8:00 PM")
    
    # Social Media
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    pinterest_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Contact Info"
        verbose_name_plural = "Contact Info"

    def save(self, *args, **kwargs):
        if not self.pk and ContactInfo.objects.exists():
            return
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

class ContactSubmission(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"
