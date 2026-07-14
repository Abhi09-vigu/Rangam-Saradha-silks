from django.contrib import admin
from .models import Category, Collection, Product, ProductImage, Review, Coupon, Cart, CartItem, Order, OrderItem

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'price', 'discount_percentage', 'offer_price', 'stock', 'is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal']
    list_filter = ['is_active', 'is_featured', 'is_trending', 'is_new_arrival', 'is_best_seller', 'is_today_deal', 'categories', 'collection']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    ordering = ['-created_at']

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
    readonly_fields = ['product', 'quantity', 'price']

class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'full_name', 'phone_number', 'payment_method', 'payment_status', 'order_status', 'grand_total', 'created_at']
    list_filter = ['payment_method', 'payment_status', 'order_status', 'created_at']
    search_fields = ['order_number', 'full_name', 'phone_number', 'email']
    inlines = [OrderItemInline]
    readonly_fields = ['order_number', 'subtotal', 'shipping_cost', 'tax_amount', 'discount_amount', 'grand_total', 'coupon_used']
    ordering = ['-created_at']

from rangam_saradha_silk.admin import custom_admin_site

custom_admin_site.register(Category, CategoryAdmin)
custom_admin_site.register(Collection, CollectionAdmin)
custom_admin_site.register(Product, ProductAdmin)
custom_admin_site.register(Review, ReviewAdmin)
custom_admin_site.register(Coupon, CouponAdmin)
custom_admin_site.register(Order, OrderAdmin)
custom_admin_site.register(Cart)
custom_admin_site.register(CartItem)
