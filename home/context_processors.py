from .models import WebsiteSetting, ContactInfo
from shop.models import Category, Cart
from decimal import Decimal


def global_context(request):
    # Safe Website Settings
    try:
        settings_obj = WebsiteSetting.objects.first()
    except Exception:
        settings_obj = None

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

    # Safe Contact Info
    try:
        contact_obj = ContactInfo.objects.first()
    except Exception:
        contact_obj = None

    if not contact_obj:
        contact_obj = ContactInfo(
            phone="+91 98765 43210",
            email="contact@rangamsaradhasilk.com",
            address="123 Silk Street, Kanchipuram, Tamil Nadu, India",
        )

    # Safe Categories
    try:
        categories = Category.objects.filter(
            is_active=True
        ).order_by("display_order")
    except Exception:
        categories = []

    cart_count = 0
    cart_total = Decimal("0.00")

    try:
        cart = None

        if request.user.is_authenticated and not request.user.is_staff:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.filter(
                    session_key=session_key
                ).first()

        if cart:
            for item in cart.items.all():
                cart_count += item.quantity
                cart_total += item.get_total_price()

    except Exception:
        cart_count = 0
        cart_total = Decimal("0.00")

    wishlist_product_ids = []
    if request.user.is_authenticated and not request.user.is_staff:
        try:
            from accounts.models import Wishlist
            wishlist_product_ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
        except Exception:
            pass

    # Dynamic dotenv check to ensure fresh credentials if .env was recently edited
    import os
    from django.conf import settings
    from dotenv import load_dotenv
    dotenv_path = settings.BASE_DIR / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=True)

    google_client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})

    return {
        "site_settings": settings_obj,
        "contact_info": contact_obj,
        "nav_categories": categories,
        "cart_count": cart_count,
        "cart_total": cart_total,
        "wishlist_product_ids": wishlist_product_ids,
        "google_client_id": google_client_id,
        "firebase_config": firebase_config,
    }