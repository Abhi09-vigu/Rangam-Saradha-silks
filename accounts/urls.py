from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('bookings/<str:booking_ref>/', views.call_booking_detail, name='booking_detail'),
    path('call-bookings/<str:booking_ref>/', views.call_booking_detail, name='call_booking_detail'),
    path('address/add/', views.address_create, name='address_add'),
    path('address/edit/<int:pk>/', views.address_edit, name='address_edit'),
    path('address/delete/<int:pk>/', views.address_delete, name='address_delete'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('change-password/', views.change_password, name='change_password'),
    path('google-login/', views.google_login_view, name='google_login'),
    path('firebase-login/', views.firebase_login_view, name='firebase_login'),
]
