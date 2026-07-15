from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<str:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<str:item_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<str:item_id>/', views.cart_remove, name='cart_remove'),
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='remove_coupon'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/create/', views.order_create, name='order_create'),
    path('order/<str:order_number>/', views.order_detail, name='order_detail'),
    path('review/add/<str:product_id>/', views.add_review, name='add_review'),
]
