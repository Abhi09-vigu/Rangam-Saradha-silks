from .models import WebsiteSetting, ContactInfo
from shop.models import Category, Cart, CartItem
from decimal import Decimal

def global_context(request):
    # Fetch or get defaults for settings
    settings_obj = WebsiteSetting.objects.first()
    if not settings_obj:
        settings_obj = WebsiteSetting(
            website_name="Rangam Saradha Silk",
            primary_color="#AF0446",
            secondary_color="#AE6F21",
            currency="₹",
            tax_percentage=0.00,
            shipping_charge=0.00,
            free_shipping_limit=1000.00,
        )
        
    contact_obj = ContactInfo.objects.first()
    if not contact_obj:
        contact_obj = ContactInfo(
            phone="+91 98765 43210",
            email="contact@rangamsaradhasilk.com",
            address="123 Silk Street, Kanchipuram, Tamil Nadu, India",
        )
        
    categories = Category.objects.filter(is_active=True).order_by('display_order')
    
    cart_count = 0
    cart_total = Decimal('0.00')
    
    # Retrieve cart
    cart = None
    if request.user.is_authenticated and not request.user.is_staff:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        session_key = request.session.session_key
        if session_key:
            cart = Cart.objects.filter(session_key=session_key).first()
            
    if cart:
        for item in cart.items.all():
            cart_count += item.quantity
            cart_total += item.get_total_price()
            
    # Check if user is logged in as staff in the admin session
    is_admin_logged_in = False
    admin_session_key = request.COOKIES.get('admin_sessionid')
    if admin_session_key:
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.auth import get_user_model
        try:
            session = SessionStore(session_key=admin_session_key)
            user_id = session.get('_auth_user_id')
            if user_id:
                User = get_user_model()
                admin_user = User.objects.get(pk=user_id)
                if admin_user.is_staff:
                    is_admin_logged_in = True
        except Exception:
            pass

    return {
        'site_settings': settings_obj,
        'contact_info': contact_obj,
        'nav_categories': categories,
        'cart_count': cart_count,
        'cart_total': cart_total,
        'is_admin_logged_in': is_admin_logged_in,
    }
