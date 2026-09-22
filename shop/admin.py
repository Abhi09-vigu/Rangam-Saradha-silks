from django.contrib import admin
from django.urls import path
from django.core.exceptions import PermissionDenied
from django.utils.html import format_html
from django.db.models import Prefetch
from .models import Category, Collection, Product, ProductImage, Review, Coupon, Cart, CartItem, Order, OrderItem

class StockStatusFilter(admin.SimpleListFilter):
    title = 'Stock Status'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'In Stock (6+)'),
            ('low_stock', 'Low Stock (1-5)'),
            ('out_of_stock', 'Out of Stock (0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'in_stock':
            return queryset.filter(stock__gte=6)
        elif self.value() == 'low_stock':
            return queryset.filter(stock__range=(1, 5))
        elif self.value() == 'out_of_stock':
            return queryset.filter(stock__lte=0)
        return queryset

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_image_thumbnail', 'name', 'sku', 'price', 'discount_percentage', 'offer_price', 'stock', 'stock_status', 'is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal']
    list_display_links = ['name']
    list_filter = [StockStatusFilter, 'is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal', 'categories', 'collection']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'sku', 'categories', 'collection', 'is_active')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'discount_percentage', 'offer_price', 'stock')
        }),
        ('Product Description', {
            'fields': ('short_description', 'description')
        }),
        ('Marketing & Flags', {
            'fields': ('is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal')
        }),
        ('Specifications & Details', {
            'fields': ('video_url', 'video_file', 'tags', 'material', 'color', 'occasion', 'fabric', 'specifications')
        }),
        ('SEO Metadata', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """
        Optimize queryset to prefetch images to avoid N+1 queries.
        """
        return super().get_queryset(request).prefetch_related('images')

    def product_image_thumbnail(self, obj):
        """
        Display a clickable 60x60 thumbnail of the product image.
        """
        images = list(obj.images.all())
        if not images or not images[0].image:
            return "No Image"
        first_image = images[0]
        return format_html(
            '<a href="{0}" target="_blank">'
            '<img src="{0}" width="60" height="60" style="object-fit: cover; border-radius: 4px; display: block; max-width: 100%;" alt="Thumbnail">'
            '</a>',
            first_image.image.url
        )
    product_image_thumbnail.short_description = "Image"

    def stock_status(self, obj):
        if obj.stock <= 0:
            color = '#AF0446' # Red
            text = 'Out of Stock'
        elif 1 <= obj.stock <= 5:
            color = '#AE6F21' # Orange
            text = f'Low Stock ({obj.stock} left)'
        else:
            color = '#1b8a53' # Green
            text = 'In Stock'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            text
        )
    stock_status.short_description = "Stock Status"


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['category_thumbnail', 'name', 'display_order', 'is_active']
    list_display_links = ['category_thumbnail', 'name']
    list_editable = ['display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

    def category_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="48" height="48" style="object-fit: cover; border-radius: 50%; border: 2px solid #C5A059;" alt="{}">',
                obj.image.url, obj.name
            )
        return format_html('<span style="color: #999;">No Image</span>')
    category_thumbnail.short_description = "Preview"

class CollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'rating']
    search_fields = ['product__name', 'user__username', 'comment']
    actions = ['approve_reviews', 'reject_reviews']

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = "Approve selected reviews"

    def reject_reviews(self, request, queryset):
        queryset.update(is_approved=False)
    reject_reviews.short_description = "Reject selected reviews"

class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'min_purchase', 'usage_limit', 'used_count', 'expiry_date', 'is_active']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code']

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ['product', 'quantity', 'price', 'item_total_display']
    readonly_fields = ['product', 'quantity', 'price', 'item_total_display']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        """
        Optimize queryset for OrderItemInline to avoid N+1 queries.
        Prefetches product and its related images.
        """
        return super().get_queryset(request).select_related('product').prefetch_related('product__images')

    def item_total_display(self, obj):
        if obj.pk and obj.price is not None and obj.quantity is not None:
            return f"₹{obj.price * obj.quantity:.2f}"
        return "-"
    item_total_display.short_description = "Item Total"

class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'product_thumbnail',
        'product_name_column',
        'order_number',
        'full_name',
        'phone_number',
        'payment_method_badge',
        'payment_status_badge',
        'razorpay_payment_id',
        'razorpay_order_id',
        'order_status_badge',
        'grand_total',
        'created_at'
    ]
    list_display_links = ['order_number']
    list_filter = ['order_status', 'payment_status', 'payment_method', 'created_at']
    search_fields = [
        'order_number', 'full_name', 'phone_number', 'tracking_number', 
        'items__product__name', 'razorpay_order_id', 'razorpay_payment_id'
    ]
    inlines = [OrderItemInline]
    readonly_fields = [
        'order_number', 'user', 'created_at', 'updated_at',
        'subtotal', 'shipping_cost', 'tax_amount', 'cod_charge', 
        'discount_amount', 'grand_total', 'coupon_used', 'gst_number',
        'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'paid_at'
    ]
    ordering = ['-created_at']
    change_form_template = 'admin/shop/order_change_form.html'
    change_list_template = 'admin/shop/order/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'monthly-report/',
                self.admin_site.admin_view(self.monthly_sales_report_view),
                name='shop_order_monthly_report',
            ),
        ]
        return custom_urls + urls

    def monthly_sales_report_view(self, request):
        if not (request.user.is_authenticated and request.user.is_staff):
            raise PermissionDenied("Only authenticated admin staff can download sales reports.")

        from django.utils import timezone
        from .reports import generate_monthly_sales_excel

        now = timezone.localtime(timezone.now())
        try:
            year = int(request.GET.get('year', now.year))
        except (ValueError, TypeError):
            year = now.year

        try:
            month = int(request.GET.get('month', now.month))
            if not (1 <= month <= 12):
                month = now.month
        except (ValueError, TypeError):
            month = now.month

        include_cancelled = request.GET.get('include_cancelled', 'false').lower() in ['true', '1', 'yes']

        return generate_monthly_sales_excel(year=year, month=month, include_cancelled=include_cancelled)


    fieldsets = (
        ('Order Status & Payment Method', {
            'fields': ('order_status', 'payment_status', 'payment_method'),
            'description': 'Update fulfillment state, payment settlement, and payment method.'
        }),
        ('Razorpay & Online Payment Details', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'paid_at'),
            'description': 'Razorpay payment gateway IDs, cryptographic signature, and payment completion timestamp.'
        }),
        ('Shipment & Tracking', {
            'fields': ('tracking_link', 'tracking_number'),
            'description': 'Enter courier tracking link and AWB/tracking number for customer shipment tracking.'
        }),
        ('Customer & Billing Details', {
            'fields': (
                'full_name', 'phone_number', 'email', 'address_line_1', 
                'address_line_2', 'city', 'state', 'pincode', 'landmark'
            ),
            'description': 'Edit customer name, contact, and delivery address for invoices.'
        }),
        ('Invoice & Financials (Locked)', {
            'fields': (
                'subtotal', 'tax_amount', 'shipping_cost', 'cod_charge', 
                'discount_amount', 'grand_total', 'coupon_used'
            ),
            'description': 'System-calculated financial amounts (locked from manual modification to preserve invoice integrity).'
        }),
        ('System Metadata', {
            'fields': ('order_number', 'user', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'order_status':
            kwargs['choices'] = [
                ('PENDING', 'Pending'),
                ('CONFIRMED', 'Confirmed'),
                ('PACKED', 'Packed'),
                ('SHIPPED', 'Shipped'),
                ('OUT_FOR_DELIVERY', 'Out For Delivery'),
                ('DELIVERED', 'Delivered'),
                ('CANCELLED', 'Cancelled'),
            ]
        elif db_field.name == 'payment_status':
            kwargs['choices'] = [
                ('PENDING', 'Pending'),
                ('PAID', 'Paid'),
                ('FAILED', 'Failed'),
                ('REFUNDED', 'Refunded'),
            ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_queryset(self, request):
        """
        Optimize queryset to fetch order items and images in bulk.
        Avoids N+1 queries when loading the order list page.
        """
        product_image_prefetch = Prefetch(
            'product__images',
            queryset=ProductImage.objects.only('id', 'product_id', 'image', 'display_order').order_by('display_order')
        )
        
        order_items_prefetch = Prefetch(
            'items',
            queryset=OrderItem.objects.select_related('product').prefetch_related(product_image_prefetch)
        )
        
        return super().get_queryset(request).prefetch_related(order_items_prefetch)

    def product_thumbnail(self, obj):
        """
        Display 60x60 product image thumbnail for the first product in the order.
        """
        items = list(obj.items.all())
        if not items or not items[0].product:
            return "No Image"
        
        images = list(items[0].product.images.all())
        if not images or not images[0].image:
            return "No Image"
            
        first_image = images[0]
        return format_html(
            '<img src="{0}" width="60" height="60" style="object-fit: cover; border-radius: 4px; display: block; max-width: 100%;" alt="Thumbnail">',
            first_image.image.url
        )
    product_thumbnail.short_description = "Product Image"

    def product_name_column(self, obj):
        """
        Display first product name. If multiple products are ordered, displays + X more items.
        """
        items = list(obj.items.all())
        if not items:
            return "No Products"
        
        first_item = items[0]
        if not first_item.product:
            return "Deleted Product"
            
        first_name = first_item.product.name
        
        extra_count = len(items) - 1
        if extra_count > 0:
            return f"{first_name} + {extra_count} more items"
        return first_name
    product_name_column.short_description = "Product Name"

    def order_status_badge(self, obj):
        """
        Render order status with a clean color badge.
        """
        status = obj.order_status
        colors = {
            'PENDING': {'bg': '#fff8eb', 'fg': '#AE6F21', 'border': '#fce8cd'},
            'CONFIRMED': {'bg': '#faf5e6', 'fg': '#8c5d1c', 'border': '#eedda6'},
            'PACKED': {'bg': '#fff0f5', 'fg': '#AF0446', 'border': '#fcd2df'},
            'SHIPPED': {'bg': '#fff5eb', 'fg': '#d96e14', 'border': '#fcdbbf'},
            'OUT_FOR_DELIVERY': {'bg': '#eefbfa', 'fg': '#0b7c8a', 'border': '#beeae6'},
            'DELIVERED': {'bg': '#f1faf5', 'fg': '#1b8a53', 'border': '#c7eed9'},
            'CANCELLED': {'bg': '#fdf3f4', 'fg': '#AF0446', 'border': '#fbd3d6'},
            'RETURNED': {'bg': '#fdf2f2', 'fg': '#9e1c24', 'border': '#fbd2d2'},
            'REFUNDED': {'bg': '#f8f9fa', 'fg': '#5f666c', 'border': '#e2e5e8'},
        }
        color = colors.get(status, {'bg': '#f8f9fa', 'fg': '#5f666c', 'border': '#e2e5e8'})
        return format_html(
            '<span style="background-color: {}; color: {}; border: 1px solid {}; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; white-space: nowrap; text-align: center;">{}</span>',
            color['bg'],
            color['fg'],
            color['border'],
            obj.get_order_status_display()
        )
    order_status_badge.short_description = "Order Status"
    order_status_badge.admin_order_field = 'order_status'

    def payment_status_badge(self, obj):
        """
        Render payment status with a clean color badge.
        """
        status = obj.payment_status
        colors = {
            'PENDING': {'bg': '#fff8eb', 'fg': '#AE6F21', 'border': '#fce8cd'},
            'PAID': {'bg': '#f1faf5', 'fg': '#1b8a53', 'border': '#c7eed9'},
            'FAILED': {'bg': '#fdf3f4', 'fg': '#AF0446', 'border': '#fbd3d6'},
            'REFUNDED': {'bg': '#f8f9fa', 'fg': '#5f666c', 'border': '#e2e5e8'},
        }
        color = colors.get(status, {'bg': '#f8f9fa', 'fg': '#5f666c', 'border': '#e2e5e8'})
        return format_html(
            '<span style="background-color: {}; color: {}; border: 1px solid {}; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; white-space: nowrap; text-align: center;">{}</span>',
            color['bg'],
            color['fg'],
            color['border'],
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = "Payment Status"
    payment_status_badge.admin_order_field = 'payment_status'

    def payment_method_badge(self, obj):
        """
        Render payment method with distinct badge distinguishing COD, Razorpay, and Offline orders.
        """
        method = obj.payment_method
        if method == 'COD':
            return format_html(
                '<span style="background-color: #fff8eb; color: #b45309; border: 1px solid #fde68a; padding: 3px 8px; border-radius: 10px; font-weight: 600; font-size: 11px; white-space: nowrap;">Cash On Delivery</span>'
            )
        elif method in ['RAZORPAY', 'ONLINE']:
            return format_html(
                '<span style="background-color: #fdf2f4; color: #8c1035; border: 1px solid #fbcfe8; padding: 3px 8px; border-radius: 10px; font-weight: 600; font-size: 11px; white-space: nowrap;">Razorpay Online</span>'
            )
        elif method == 'OFFLINE':
            return format_html(
                '<span style="background-color: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; padding: 3px 8px; border-radius: 10px; font-weight: 600; font-size: 11px; white-space: nowrap;">Offline Store</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; padding: 3px 8px; border-radius: 10px; font-weight: 600; font-size: 11px; white-space: nowrap;">{}</span>',
                obj.get_payment_method_display() or method
            )
    payment_method_badge.short_description = "Payment Method"
    payment_method_badge.admin_order_field = 'payment_method'

from django.utils.html import format_html
from .models import Category, Collection, Product, ProductImage, Review, Coupon, Cart, CartItem, Order, OrderItem, CallBooking, CallSlot


class CallSlotAdmin(admin.ModelAdmin):
    list_display = ['date', 'time_slot', 'effective_status_badge', 'blocked_by_owner', 'booked_customer', 'related_product', 'notes', 'updated_at']
    list_filter = ['blocked_by_owner', 'status', 'date', 'time_slot']
    search_fields = ['notes', 'date']
    list_editable = ['blocked_by_owner']
    ordering = ['date', 'time_slot']
    actions = ['mark_as_blocked', 'mark_as_unblocked']

    def effective_status_badge(self, obj):
        st = obj.get_effective_status()
        if st == 'BLOCKED':
            return format_html('<span style="background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px;">🔴 BLOCKED (Owner)</span>')
        elif st == 'BOOKED':
            return format_html('<span style="background-color: #ffeeba; color: #856404; border: 1px solid #ffeeba; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px;">🔒 BLOCKED (Booked)</span>')
        return format_html('<span style="background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px;">🟢 AVAILABLE</span>')

    effective_status_badge.short_description = "Status"

    def booked_customer(self, obj):
        booking = CallBooking.objects.filter(booking_date=obj.date, time_slot=obj.time_slot, status__in=['CONFIRMED', 'COMPLETED']).first()
        if booking:
            return f"{booking.full_name} ({booking.phone_number})"
        return "-"

    booked_customer.short_description = "Customer"

    def related_product(self, obj):
        booking = CallBooking.objects.filter(booking_date=obj.date, time_slot=obj.time_slot, status__in=['CONFIRMED', 'COMPLETED']).first()
        if booking and booking.product:
            return booking.product.name
        return "-"

    related_product.short_description = "Product"

    def mark_as_blocked(self, request, queryset):
        rows = queryset.update(blocked_by_owner=True, status='BLOCKED')
        self.message_user(request, f"{rows} time slot(s) successfully marked as BLOCKED.")

    mark_as_blocked.short_description = "Block selected slots (Owner Unavailable)"

    def mark_as_unblocked(self, request, queryset):
        rows = queryset.update(blocked_by_owner=False, status='AVAILABLE')
        self.message_user(request, f"{rows} time slot(s) successfully unblocked.")

    mark_as_unblocked.short_description = "Unblock selected slots (Make Available)"


class CallBookingAdmin(admin.ModelAdmin):
    list_display = ['booking_reference', 'full_name', 'phone_number', 'saree_display', 'product_sku', 'booking_date', 'time_slot', 'fee_amount', 'payment_status_badge', 'payment_method', 'status', 'created_at']
    list_filter = ['payment_status', 'payment_method', 'status', 'booking_date', 'time_slot']
    search_fields = ['booking_reference', 'full_name', 'email', 'phone_number', 'saree_preference', 'product__name', 'product__sku', 'payment_reference']
    readonly_fields = ['booking_reference', 'payment_reference', 'created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    actions = ['mark_as_completed', 'mark_as_cancelled', 'mark_as_confirmed']

    def saree_display(self, obj):
        if obj.product:
            return obj.product.name
        return obj.saree_preference or "General Consultation"
    saree_display.short_description = "Saree / Product"

    def product_sku(self, obj):
        return obj.product.sku if obj.product and obj.product.sku else "-"
    product_sku.short_description = "SKU"

    def payment_status_badge(self, obj):
        if obj.payment_status == 'PAID':
            return format_html('<span style="background-color: #d1e7dd; color: #0f5132; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">PAID</span>')
        elif obj.payment_status == 'PENDING':
            return format_html('<span style="background-color: #fff3cd; color: #664d03; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">PENDING</span>')
        elif obj.payment_status == 'FAILED':
            return format_html('<span style="background-color: #f8d7da; color: #842029; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">FAILED</span>')
        return format_html('<span style="background-color: #e2e3e5; color: #41464b; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">{}</span>', obj.payment_status)
    payment_status_badge.short_description = "Payment"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == 'CANCELLED':
            has_other = CallBooking.objects.filter(
                booking_date=obj.booking_date,
                time_slot=obj.time_slot,
                status__in=['CONFIRMED', 'COMPLETED']
            ).exclude(pk=obj.pk).exists()
            if not has_other:
                CallSlot.objects.filter(date=obj.booking_date, time_slot=obj.time_slot, blocked_by_owner=False).update(status='AVAILABLE')
        elif obj.status in ['CONFIRMED', 'COMPLETED']:
            CallSlot.objects.update_or_create(
                date=obj.booking_date,
                time_slot=obj.time_slot,
                defaults={'status': 'BOOKED'}
            )

    def delete_model(self, request, obj):
        booking_date = obj.booking_date
        time_slot = obj.time_slot
        super().delete_model(request, obj)
        if not CallBooking.objects.filter(booking_date=booking_date, time_slot=time_slot, status__in=['CONFIRMED', 'COMPLETED']).exists():
            CallSlot.objects.filter(date=booking_date, time_slot=time_slot, blocked_by_owner=False).update(status='AVAILABLE')

    def delete_queryset(self, request, queryset):
        slots_to_check = list(queryset.values_list('booking_date', 'time_slot').distinct())
        super().delete_queryset(request, queryset)
        for booking_date, time_slot in slots_to_check:
            if not CallBooking.objects.filter(booking_date=booking_date, time_slot=time_slot, status__in=['CONFIRMED', 'COMPLETED']).exists():
                CallSlot.objects.filter(date=booking_date, time_slot=time_slot, blocked_by_owner=False).update(status='AVAILABLE')

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='COMPLETED')
        self.message_user(request, f"{updated} booking(s) marked as Completed.")
    mark_as_completed.short_description = "Mark selected as Completed"

    def mark_as_cancelled(self, request, queryset):
        for b in queryset:
            b.status = 'CANCELLED'
            b.save()
            has_other = CallBooking.objects.filter(
                booking_date=b.booking_date,
                time_slot=b.time_slot,
                status__in=['CONFIRMED', 'COMPLETED']
            ).exclude(pk=b.pk).exists()
            if not has_other:
                CallSlot.objects.filter(date=b.booking_date, time_slot=b.time_slot, blocked_by_owner=False).update(status='AVAILABLE')
        self.message_user(request, f"{queryset.count()} booking(s) marked as Cancelled.")
    mark_as_cancelled.short_description = "Mark selected as Cancelled (Unblocks Slot)"

    def mark_as_confirmed(self, request, queryset):
        for b in queryset:
            b.status = 'CONFIRMED'
            b.save()
            CallSlot.objects.update_or_create(
                date=b.booking_date,
                time_slot=b.time_slot,
                defaults={'status': 'BOOKED'}
            )
        self.message_user(request, f"{queryset.count()} booking(s) marked as Confirmed.")
    mark_as_confirmed.short_description = "Mark selected as Confirmed (Blocks Slot)"


from rangam_saradha_silk.admin import custom_admin_site

custom_admin_site.register(Category, CategoryAdmin)
custom_admin_site.register(Collection, CollectionAdmin)
custom_admin_site.register(Product, ProductAdmin)
custom_admin_site.register(Review, ReviewAdmin)
custom_admin_site.register(Coupon, CouponAdmin)
custom_admin_site.register(Order, OrderAdmin)
custom_admin_site.register(CallBooking, CallBookingAdmin)
custom_admin_site.register(CallSlot, CallSlotAdmin)
custom_admin_site.register(Cart)
custom_admin_site.register(CartItem)

