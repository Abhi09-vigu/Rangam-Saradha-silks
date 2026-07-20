from django.contrib import admin
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
            return queryset.filter(stock=0)
        return queryset

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_image_thumbnail', 'name', 'sku', 'price', 'discount_percentage', 'offer_price', 'stock', 'stock_status', 'is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal']
    list_filter = [StockStatusFilter, 'is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal', 'categories', 'collection']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    ordering = ['-created_at']

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
        if obj.stock == 0:
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
    list_display = ['name', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

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
    readonly_fields = ['product_image', 'product_name', 'quantity', 'price', 'total_price']
    fields = ['product_image', 'product_name', 'quantity', 'price', 'total_price']

    def get_queryset(self, request):
        """
        Optimize queryset for OrderItemInline to avoid N+1 queries.
        Prefetches product and its related images.
        """
        return super().get_queryset(request).select_related('product').prefetch_related('product__images')

    def product_image(self, obj):
        """
        Display a clickable 60x60 thumbnail of the product in the inline.
        """
        if not obj.product:
            return "No Image"
        
        images = list(obj.product.images.all())
        if not images or not images[0].image:
            return "No Image"
            
        first_image = images[0]
        return format_html(
            '<a href="{0}" target="_blank">'
            '<img src="{0}" width="60" height="60" style="object-fit: cover; border-radius: 4px; display: block; max-width: 100%;" alt="Thumbnail">'
            '</a>',
            first_image.image.url
        )
    product_image.short_description = "Product Image"

    def product_name(self, obj):
        """
        Display product name or Deleted Product if product is missing.
        """
        if obj.product:
            return obj.product.name
        return "Deleted Product"
    product_name.short_description = "Product Name"

    def total_price(self, obj):
        """
        Calculate total price for the item (quantity * price).
        """
        return f"₹{obj.price * obj.quantity}"
    total_price.short_description = "Total"

class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'product_thumbnail',
        'product_name_column',
        'order_number',
        'full_name',
        'phone_number',
        'payment_method',
        'payment_status_badge',
        'order_status_badge',
        'grand_total',
        'created_at'
    ]
    list_filter = ['order_status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'full_name', 'phone_number', 'items__product__name']
    inlines = [OrderItemInline]
    readonly_fields = ['order_number', 'subtotal', 'shipping_cost', 'tax_amount', 'cod_charge', 'discount_amount', 'grand_total', 'coupon_used']
    ordering = ['-created_at']

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
        Display 60x60 clickable product image thumbnail for the first product in the order.
        """
        items = list(obj.items.all())
        if not items or not items[0].product:
            return "No Image"
        
        images = list(items[0].product.images.all())
        if not images or not images[0].image:
            return "No Image"
            
        first_image = images[0]
        return format_html(
            '<a href="{0}" target="_blank">'
            '<img src="{0}" width="60" height="60" style="object-fit: cover; border-radius: 4px; display: block; max-width: 100%;" alt="Thumbnail">'
            '</a>',
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
        first_name = first_item.product.name if first_item.product else "Deleted Product"
        
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

from rangam_saradha_silk.admin import custom_admin_site

custom_admin_site.register(Category, CategoryAdmin)
custom_admin_site.register(Collection, CollectionAdmin)
custom_admin_site.register(Product, ProductAdmin)
custom_admin_site.register(Review, ReviewAdmin)
custom_admin_site.register(Coupon, CouponAdmin)
custom_admin_site.register(Order, OrderAdmin)
custom_admin_site.register(Cart)
custom_admin_site.register(CartItem)
