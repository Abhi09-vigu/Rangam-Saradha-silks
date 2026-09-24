from django.db import models
from django.conf import settings
from django.utils.text import slugify
import datetime
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

class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True)
    categories = models.ManyToManyField(Category, related_name='products')
    
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
    zari_type = models.CharField(max_length=150, blank=True, default="Premium Gold Zari Traditional Weave", help_text="Zari specification (e.g., Premium Gold Zari Traditional Weave)")
    saree_length = models.CharField(max_length=150, blank=True, default="5.5 Meters (Approx.) + 0.8 Meter Running Blouse", help_text="Length specification (e.g., 5.5 Meters + 0.8 Meter Running Blouse)")
    authenticity = models.CharField(max_length=200, blank=True, default="Silk Mark Certified 100% Handcrafted Mulberry Silk", help_text="Certification / Authenticity (e.g., Silk Mark Certified)")
    specifications = models.TextField(blank=True, default="", help_text="Additional specifications in plain text (enter one per line, e.g., 'Blouse: Contrast Brocade' or 'Border: Temple Border')")
    
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
        if self.price is not None:
            price_decimal = Decimal(str(self.price))
            if price_decimal > Decimal('0'):
                if self.offer_price is not None:
                    offer_decimal = Decimal(str(self.offer_price))
                    if offer_decimal < price_decimal:
                        calculated_discount = ((price_decimal - offer_decimal) / price_decimal) * Decimal('100')
                        self.discount_percentage = int(calculated_discount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    else:
                        self.discount_percentage = 0
                        self.offer_price = price_decimal
                elif self.discount_percentage > 0:
                    disc_decimal = Decimal(str(self.discount_percentage))
                    calc_offer = price_decimal - (price_decimal * disc_decimal / Decimal('100'))
                    self.offer_price = calc_offer.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                else:
                    self.offer_price = price_decimal
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    @property
    def parsed_specifications(self):
        """
        Parses text specifications into a list of (label, value) tuples.
        Supports 'Key: Value' format or plain descriptive lines.
        Deduplicates against dedicated model fields (Fabric, Color, Material, etc.) to prevent duplicate rows.
        """
        if not self.specifications:
            return []
        if isinstance(self.specifications, dict):
            raw_items = list(self.specifications.items())
        else:
            raw_items = []
            for line in str(self.specifications).splitlines():
                line = line.strip()
                if not line:
                    continue
                if ':' in line:
                    key, val = line.split(':', 1)
                    raw_items.append((key.strip(), val.strip()))
                else:
                    raw_items.append(('Specification', line))

        import re
        def normalize_key(k):
            return re.sub(r'[^a-z0-9]', '', str(k).lower())

        # Collect keys that are already displayed via direct model fields
        existing_keys = set()
        if self.fabric:
            existing_keys.add(normalize_key('Fabric'))
            existing_keys.add(normalize_key('Fabric Type'))
            existing_keys.add(normalize_key('Saree Fabric'))
        if self.color:
            existing_keys.add(normalize_key('Color'))
            existing_keys.add(normalize_key('Colour'))
        if self.material:
            existing_keys.add(normalize_key('Material'))
        if self.occasion:
            existing_keys.add(normalize_key('Occasion'))
        if self.zari_type:
            existing_keys.add(normalize_key('Zari Type'))
            existing_keys.add(normalize_key('Zari'))
        if self.saree_length:
            existing_keys.add(normalize_key('Saree Length'))
            existing_keys.add(normalize_key('Length'))
        if self.authenticity:
            existing_keys.add(normalize_key('Authenticity'))

        items = []
        for key, val in raw_items:
            k_norm = normalize_key(key)
            if k_norm in existing_keys:
                continue
            existing_keys.add(k_norm)
            items.append((key.strip(), val.strip()))

        return items

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
    APPLY_TO_CHOICES = (
        ('ALL', 'All Products'),
        ('CATEGORIES', 'Specific Categories'),
        ('PRODUCTS', 'Specific Products'),
    )

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=(('PERCENT', 'Percentage'), ('FIXED', 'Fixed Amount')), default='PERCENT')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Maximum discount for Percentage type")
    usage_limit = models.IntegerField(default=100)
    used_count = models.IntegerField(default=0)
    start_date = models.DateField(default=datetime.date.today, null=True, blank=True, help_text="Start date from which this coupon becomes valid")
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)

    # Targeting
    apply_to = models.CharField(max_length=20, choices=APPLY_TO_CHOICES, default='ALL', help_text="Choose where this coupon can be applied")
    categories = models.ManyToManyField(Category, blank=True, related_name='coupons', help_text="Categories eligible for this coupon")
    products = models.ManyToManyField(Product, blank=True, related_name='coupons', help_text="Products eligible for this coupon")

    def get_eligible_items(self, cart):
        """
        Returns a list of CartItem instances from the cart that are eligible for this coupon.
        """
        if not cart:
            return []

        if hasattr(cart, 'items'):
            items = list(cart.items.select_related('product').prefetch_related('product__categories').all())
        elif isinstance(cart, (list, tuple)):
            items = list(cart)
        else:
            return []

        if self.apply_to == 'ALL':
            return [item for item in items if item.product and item.product.is_active and item.product.stock > 0]

        elif self.apply_to == 'CATEGORIES':
            eligible_cat_ids = set(self.categories.values_list('id', flat=True))
            eligible = []
            for item in items:
                if not item.product or not item.product.is_active or item.product.stock <= 0:
                    continue
                product_cat_ids = set(item.product.categories.values_list('id', flat=True))
                if eligible_cat_ids & product_cat_ids:
                    eligible.append(item)
            return eligible

        elif self.apply_to == 'PRODUCTS':
            eligible_prod_ids = set(self.products.values_list('id', flat=True))
            eligible = [
                item for item in items
                if item.product and item.product_id in eligible_prod_ids and item.product.is_active and item.product.stock > 0
            ]
            return eligible

        return items

    def is_valid(self, cart_total, cart=None):
        today = datetime.date.today()
        start = self.start_date.date() if isinstance(self.start_date, datetime.datetime) else self.start_date
        expiry = self.expiry_date.date() if isinstance(self.expiry_date, datetime.datetime) else self.expiry_date
        if not self.is_active:
            return False
        if start and start > today:
            return False
        if expiry and expiry < today:
            return False
        if self.used_count >= self.usage_limit:
            return False
        if Decimal(str(cart_total or 0)) < Decimal(str(self.min_purchase or 0)):
            return False
        if cart is not None and self.apply_to in ('CATEGORIES', 'PRODUCTS'):
            eligible_items = self.get_eligible_items(cart)
            if not eligible_items:
                return False
        return True

    def calculate_discount(self, cart_total, cart=None):
        cart_total = Decimal(str(cart_total or 0))

        if cart is not None and self.apply_to in ('CATEGORIES', 'PRODUCTS'):
            eligible_items = self.get_eligible_items(cart)
            if not eligible_items:
                return Decimal('0.00')
            discount_base = sum(Decimal(str(item.get_total_price())) for item in eligible_items)
        else:
            discount_base = cart_total

        if discount_base <= Decimal('0.00'):
            return Decimal('0.00')

        if self.discount_type == 'PERCENT':
            disc_rate = Decimal(str(self.discount_value)) / Decimal('100.00')
            discount = (discount_base * disc_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if self.max_discount and discount > Decimal(str(self.max_discount)):
                discount = Decimal(str(self.max_discount))
            return min(discount, discount_base)
        else:
            fixed_val = Decimal(str(self.discount_value))
            return min(fixed_val, discount_base)

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

    @staticmethod
    def get_configured_tax_rate():
        from home.models import WebsiteSetting
        settings_obj = WebsiteSetting.objects.first()
        if settings_obj and settings_obj.tax_percentage is not None:
            tax_pct = Decimal(str(settings_obj.tax_percentage))
            if tax_pct > Decimal('0.00'):
                return tax_pct / Decimal('100.00')
        return Decimal('0.00')

    def get_unit_price_with_tax(self, tax_rate=None):
        if tax_rate is None:
            tax_rate = self.get_configured_tax_rate()
        else:
            tax_rate = Decimal(str(tax_rate))
        unit_price = Decimal(str(self.product.offer_price))
        if tax_rate > Decimal('0.00'):
            return (unit_price * (Decimal('1.00') + tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return unit_price

    def get_total_price_with_tax(self, tax_rate=None):
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


class BulkStockProduct(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('REVIEW', 'Under Review'),
        ('PUBLISHED', 'Published'),
    )

    name = models.CharField(max_length=200, blank=True, default='')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='bulk_stock_products')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, blank=True, default='')
    stock = models.IntegerField(default=1)
    image = models.ImageField(upload_to='bulk_stock/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # Marketing Flags
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_today_deal = models.BooleanField(default=False)

    # Media & Tags
    video_url = models.URLField(max_length=500, blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, default='')

    # Product Specifications & Details
    short_description = models.TextField(max_length=500, blank=True, default='')
    description = models.TextField(blank=True, default='')
    fabric = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=100, blank=True, default='')
    material = models.CharField(max_length=100, blank=True, default='')
    occasion = models.CharField(max_length=100, blank=True, default='')
    zari_type = models.CharField(max_length=150, blank=True, default="Premium Gold Zari Traditional Weave")
    saree_length = models.CharField(max_length=150, blank=True, default="5.5 Meters (Approx.) + 0.8 Meter Running Blouse")
    authenticity = models.CharField(max_length=200, blank=True, default="Silk Mark Certified 100% Handcrafted Mulberry Silk")
    specifications = models.TextField(blank=True, default='')

    # SEO Metadata
    meta_title = models.CharField(max_length=150, blank=True, default='')
    meta_description = models.TextField(blank=True, default='')
    meta_keywords = models.CharField(max_length=255, blank=True, default='')

    # Status and User Tracking
    status = models.CharField(max_length=20, default='DRAFT', choices=STATUS_CHOICES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='bulk_stock_items')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bulk Stock"
        verbose_name_plural = "Bulk Stock"
        ordering = ['id']

    def __str__(self):
        return self.name or f"Draft #{self.id}"


class BulkStockProductImage(models.Model):
    bulk_product = models.ForeignKey(BulkStockProduct, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='bulk_stock/')
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"Image for {self.bulk_product}"



