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
    if hasattr(request, 'user') and request.user.is_authenticated and not request.user.is_staff:
        try:
            from accounts.models import Wishlist
            wishlist_product_ids = list(Wishlist.objects.filter(user=request.user, product__is_active=True, product__stock__gt=0).values_list('product_id', flat=True))
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

    active_popup = None
    try:
        from django.db import models
        from django.utils import timezone
        from home.models import Popup
        now = timezone.now()
        active_popup = Popup.objects.filter(
            is_active=True
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        ).order_by('-priority', '-created_at').first()
    except Exception:
        active_popup = None

    # Mandatory TEMP POPUP / Launch Lock evaluation
    is_staff = False
    if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        is_staff = True
    else:
        admin_session_key = request.COOKIES.get('admin_sessionid')
        if admin_session_key:
            from django.contrib.sessions.backends.db import SessionStore
            from django.contrib.auth import get_user_model
            try:
                session = SessionStore(session_key=admin_session_key)
                user_id = session.get('_auth_user_id')
                if user_id:
                    User = get_user_model()
                    admin_user = User.objects.filter(pk=user_id).first()
                    if admin_user and (admin_user.is_staff or admin_user.is_superuser):
                        is_staff = True
            except Exception:
                pass

    show_temp_popup = False
    temp_popup_target_ms = 0
    temp_popup_iso = ""
    temp_popup_days = "00"
    temp_popup_hours = "00"
    temp_popup_minutes = "00"
    temp_popup_seconds = "00"

    # Only show to non-staff and outside Django admin, and NEVER to search engine crawlers
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_bot = any(bot in user_agent for bot in ['googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider', 'yandexbot', 'sogou', 'exabot', 'facebot', 'ia_archiver'])

    if not is_staff and not is_bot and not request.path.startswith('/admin/'):
        override = getattr(settings, 'LAUNCH_MODE_OVERRIDE', None) or os.environ.get('LAUNCH_MODE_OVERRIDE')
        is_active_now = False
        if override == 'launched':
            is_active_now = False
        elif override == 'locked':
            is_active_now = True
        elif settings_obj and getattr(settings_obj, 'is_temp_popup_active', False):
            is_active_now = True

        if is_active_now or request.GET.get('preview_temp_popup') == '1':
            show_temp_popup = True
            from zoneinfo import ZoneInfo
            from datetime import datetime
            kolkata = ZoneInfo("Asia/Kolkata")
            target_dt = getattr(settings_obj, 'launch_datetime', None) or datetime(2026, 9, 25, 10, 30, 0, tzinfo=kolkata)
            temp_popup_target_ms = int(target_dt.timestamp() * 1000)
            temp_popup_iso = target_dt.isoformat()

            from django.utils import timezone
            diff = target_dt - timezone.now()
            total_sec = max(0, int(diff.total_seconds()))
            temp_popup_days = f"{total_sec // 86400:02d}"
            temp_popup_hours = f"{(total_sec % 86400) // 3600:02d}"
            temp_popup_minutes = f"{(total_sec % 3600) // 60:02d}"
            temp_popup_seconds = f"{total_sec % 60:02d}"

    return {
        "site_settings": settings_obj,
        "contact_info": contact_obj,
        "nav_categories": categories,
        "cart_count": cart_count,
        "cart_total": cart_total,
        "wishlist_product_ids": wishlist_product_ids,
        "google_client_id": google_client_id,
        "firebase_config": firebase_config,
        "active_popup": active_popup,
        "show_temp_popup": show_temp_popup,
        "temp_popup_target_ms": temp_popup_target_ms,
        "temp_popup_iso": temp_popup_iso,
        "temp_popup_days": temp_popup_days,
        "temp_popup_hours": temp_popup_hours,
        "temp_popup_minutes": temp_popup_minutes,
        "temp_popup_seconds": temp_popup_seconds,
    }