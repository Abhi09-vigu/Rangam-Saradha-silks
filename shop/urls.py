from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('categories/', views.categories_list, name='categories'),
    path('category/<slug:category_slug>/', views.catalog, name='category_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:item_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='coupon_remove'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/create/', views.order_create, name='order_create'),
    path('order/<str:order_number>/', views.order_detail, name='order_detail'),
    path('review/add/<int:product_id>/', views.add_review, name='add_review'),
    
    # Compare and Quick View URLs
    path('compare/', views.compare_page, name='compare_page'),
    path('compare/add/<int:product_id>/', views.compare_add, name='compare_add'),
    path('compare/remove/<int:product_id>/', views.compare_remove, name='compare_remove'),
    path('product/<int:product_id>/quick-view/', views.product_quick_view, name='product_quick_view'),
    
    # Book a Call URLs
    path('product/<slug:slug>/book-call/', views.book_call, name='book_call'),
    path('booking/confirmation/<str:booking_ref>/', views.booking_confirmation, name='booking_confirmation'),
    path('api/slot-availability/', views.slot_availability_api, name='slot_availability_api'),
]
