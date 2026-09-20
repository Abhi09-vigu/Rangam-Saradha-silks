from django.db import models
from django.conf import settings
from django.utils.text import slugify
from decimal import Decimal, ROUND_HALF_UP
from cloudinary_storage.storage import VideoMediaCloudinaryStorage

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='categories/')
    banner = models.ImageField(upload_to='category_banners/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # SEO
    meta_title = models.CharField(max_length=150, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    meta_keywords = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['display_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:category_detail', kwargs={'category_slug': self.slug})

    def __str__(self):
        return self.name

class Collection(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='collections/', blank=True, null=True, help_text="Cover image for this collection on the homepage.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True)
    categories = models.ManyToManyField(Category, related_name='products')
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    short_description = models.TextField(max_length=500, blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.IntegerField(default=0, help_text="Discount percentage (e.g. 10 for 10%)")
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Calculated automatically if left blank")
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Flags
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_today_deal = models.BooleanField(default=False)
    
    # Product Specs
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="External video URL (YouTube, Vimeo, etc.)")
    video_file = models.FileField(upload_to='product_videos/', storage=VideoMediaCloudinaryStorage(), max_length=500, blank=True, null=True, help_text="Direct video file upload (MP4, WebM, MOV)")
    tags = models.CharField(max_length=255, blank=True, null=True, help_text="Comma-separated tags")
    material = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    occasion = models.CharField(max_length=100, blank=True, null=True)
    fabric = models.CharField(max_length=100, blank=True, null=True)
    specifications = models.JSONField(default=dict, blank=True, help_text="Key-value specifications (e.g., {'Zari Type': 'Pure Gold', 'Blouse': 'Contrast'})")
    
    # SEO
    meta_title = models.CharField(max_length=150, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    meta_keywords = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.offer_price is None:
            if self.discount_percentage > 0:
                price_decimal = Decimal(str(self.price))
                self.offer_price = price_decimal - (price_decimal * Decimal(self.discount_percentage) / Decimal('100'))
            else:
                self.offer_price = self.price
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name

    @property
    def has_video(self):
        return bool(self.video_file or self.video_url)

    @property
    def embed_video_url(self):
        if self.video_file:
            return self.video_file.url
        if not self.video_url:
            return ''
        url = self.video_url.strip()
        import re
        
        # YouTube Shorts
        match_shorts = re.search(r'(?:youtube\.com|youtu\.be)/shorts/([a-zA-Z0-9_-]+)', url)
        if match_shorts:
            return f"https://www.youtube.com/embed/{match_shorts.group(1)}"
        
        # YouTube Standard Watch / Embed / Shortened
        match_yt = re.search(r'(?:v=|/embed/|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if match_yt:
            return f"https://www.youtube.com/embed/{match_yt.group(1)}"

        # Vimeo
        match_vimeo = re.search(r'(?:vimeo\.com/|player\.vimeo\.com/video/)([0-9]+)', url)
        if match_vimeo:
            return f"https://player.vimeo.com/video/{match_vimeo.group(1)}"

        return url

    @property
    def is_direct_video_file(self):
        if self.video_file:
            return True
        if not self.video_url:
            return False
        url = self.video_url.strip().lower()
        return url.endswith(('.mp4', '.webm', '.ogg', '.mov', '.m4v'))

    @property
    def approved_reviews(self):
        return self.reviews.filter(is_approved=True)

    @property
    def review_count(self):
        return self.approved_reviews.count()

    @property
    def average_rating(self):
        approved = self.approved_reviews
        if approved.exists():
            from django.db.models import Avg
            avg = approved.aggregate(Avg('rating'))['rating__avg']
            return round(avg, 1) if avg else 0
        return 0

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    image = models.ImageField(upload_to='reviews/', blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating} Stars)"

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=(('PERCENT', 'Percentage'), ('FIXED', 'Fixed Amount')), default='PERCENT')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Maximum discount for Percentage type")
    usage_limit = models.IntegerField(default=100)
    used_count = models.IntegerField(default=0)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def is_valid(self, cart_total):
        import datetime
        if not self.is_active:
            return False
        if self.expiry_date < datetime.date.today():
            return False
        if self.used_count >= self.usage_limit:
            return False
        if cart_total < self.min_purchase:
            return False
        return True

    def calculate_discount(self, cart_total):
        if self.discount_type == 'PERCENT':
            discount = cart_total * (self.discount_value / Decimal('100'))
            if self.max_discount and discount > self.max_discount:
                discount = self.max_discount
            return discount
        else:
            return min(self.discount_value, cart_total)

    def __str__(self):
        return self.code

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.id} - User: {self.user or 'Anonymous'}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        return self.product.offer_price * self.quantity

    def get_unit_price_with_tax(self, tax_rate=Decimal('0.05')):
        unit_price = Decimal(str(self.product.offer_price))
        return (unit_price * (Decimal('1.00') + tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_total_price_with_tax(self, tax_rate=Decimal('0.05')):
        return (self.get_unit_price_with_tax(tax_rate) * self.quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PACKED', 'Packed'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out For Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('RETURNED', 'Returned'),
        ('REFUNDED', 'Refunded'),
    )
    
    PAYMENT_METHODS = (
        ('COD', 'Cash On Delivery'),
        ('RAZORPAY', 'Pay Online (Razorpay)'),
        ('ONLINE', 'Online Payment (Razorpay)'),
        ('OFFLINE', 'Offline Store'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True)
    
    # Billing/Shipping Info
    full_name = models.CharField(max_length=150)
    gst_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Billing GST Number / GSTIN", 
        help_text="Customer or Business GSTIN for billing invoice"
    )
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    landmark = models.CharField(max_length=100, blank=True, null=True)
    
    # Payment / Order Details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='COD')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    order_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Razorpay Payment Details
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Razorpay Order ID")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Razorpay Payment ID")
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True, verbose_name="Razorpay Signature")
    paid_at = models.DateTimeField(blank=True, null=True, verbose_name="Paid At")
    
    # Shipment Tracking
    tracking_link = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Tracking Link",
        help_text="Direct URL to track the courier shipment"
    )
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Tracking / AWB Number",
        help_text="Consignment number or AWB number"
    )
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)

    
    coupon_used = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_number}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at the time of purchase")

    def get_total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product.name if self.product else 'Deleted Product'} ({self.quantity})"

class CallBooking(models.Model):
    TIME_SLOT_CHOICES = (
        ('10:00 AM - 11:00 AM', '10:00 AM - 11:00 AM'),
        ('11:00 AM - 12:00 PM', '11:00 AM - 12:00 PM'),
        ('02:00 PM - 03:00 PM', '02:00 PM - 03:00 PM'),
        ('04:00 PM - 05:00 PM', '04:00 PM - 05:00 PM'),
        ('06:00 PM - 07:00 PM', '06:00 PM - 07:00 PM'),
    )

    STATUS_CHOICES = (
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('UPI', 'UPI / QR Code'),
        ('CARD', 'Credit / Debit Card'),
        ('NETBANKING', 'Net Banking'),
        ('ONLINE', 'Online Payment'),
    )

    booking_reference = models.CharField(max_length=20, unique=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_bookings')
    saree_preference = models.CharField(max_length=255, blank=True, null=True, help_text="Saree or product of interest from general booking")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_bookings')
    
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default='')
    phone_number = models.CharField(max_length=20)
    booking_date = models.DateField()
    time_slot = models.CharField(max_length=50, choices=TIME_SLOT_CHOICES)
    notes = models.TextField(blank=True, null=True, help_text="Specific requirements or questions for the call")
    
    # Payment / Fee Details (Nominal ₹50 reservation fee)
    fee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=50.00, help_text="Consultation fee in INR")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PAID')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='UPI')
    payment_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Payment transaction or UPI reference ID")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Call Booking"
        verbose_name_plural = "Call Bookings"

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import uuid
            self.booking_reference = f"BK-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        prod_label = self.product.name if self.product else (self.saree_preference or 'General Consultation')
        return f"Book a Call #{self.booking_reference} - {self.full_name} ({prod_label})"


class CallSlot(models.Model):
    SLOT_STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('BOOKED', 'Booked'),
        ('BLOCKED', 'Blocked'),
    )

    date = models.DateField()
    time_slot = models.CharField(max_length=50, choices=CallBooking.TIME_SLOT_CHOICES)
    status = models.CharField(max_length=20, choices=SLOT_STATUS_CHOICES, default='AVAILABLE')
    blocked_by_owner = models.BooleanField(default=False, help_text="Mark True to block this slot (owner unavailable/busy)")
    notes = models.CharField(max_length=255, blank=True, null=True, help_text="Optional note / reason for blocking")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'time_slot']
        unique_together = ['date', 'time_slot']
        verbose_name = "Call Slot"
        verbose_name_plural = "Call Slots"

    def get_effective_status(self):
        """
        Computes effective slot status:
        - If blocked_by_owner or status == 'BLOCKED' -> BLOCKED
        - Else if active booking exists (CONFIRMED, COMPLETED) -> BOOKED
        - Else -> AVAILABLE
        """
        if self.blocked_by_owner or self.status == 'BLOCKED':
            return 'BLOCKED'
        
        active_booking = CallBooking.objects.filter(
            booking_date=self.date,
            time_slot=self.time_slot,
            status__in=['CONFIRMED', 'COMPLETED']
        ).first()
        
        if active_booking:
            return 'BOOKED'
            
        return 'AVAILABLE'

    def __str__(self):
        return f"{self.date} ({self.time_slot}) - {self.get_status_display()}"


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=CallBooking)
def release_call_slot_on_booking_delete(sender, instance, **kwargs):
    """
    When a CallBooking is deleted (from admin, API, or shell),
    check if any other active booking exists for the slot.
    If not, release the CallSlot so it shows as AVAILABLE.
    """
    has_active = CallBooking.objects.filter(
        booking_date=instance.booking_date,
        time_slot=instance.time_slot,
        status__in=['CONFIRMED', 'COMPLETED']
    ).exists()
    if not has_active:
        CallSlot.objects.filter(
            date=instance.booking_date,
            time_slot=instance.time_slot,
            blocked_by_owner=False
        ).update(status='AVAILABLE')


