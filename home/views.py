import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import WebsiteSetting, ContactInfo, HeroSlider, OfferBanner, Testimonial, CMSPage, FAQ, InstagramPost, ContactMessage, ContactSubmission, BudgetRange, WhyChooseUs, FabricCuration
from .serializers import ContactMessageSerializer
from shop.models import Category, Product
from shop.views import apply_sku_priority_and_sorting

logger = logging.getLogger(__name__)

class ContactFormAPIView(APIView):
    """
    API endpoint for Contact Us form submission.
    POST /api/contact/
    """
    def post(self, request, *args, **kwargs):
        serializer = ContactMessageSerializer(data=request.data)
        if not serializer.is_valid():
            error_details = []
            for field, errors in serializer.errors.items():
                for error in errors:
                    error_details.append(f"{field.capitalize()}: {error}")
            error_msg = error_details[0] if error_details else "Validation error."
            return Response(
                {
                    "success": False,
                    "message": error_msg,
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save to database
        contact_message = serializer.save()

        # Format submission time
        formatted_time = contact_message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Email notification setup
        phone_line = f"Phone Number: {contact_message.phone_number}\n" if contact_message.phone_number else ""
        email_subject = f"New Contact Form Submission - {contact_message.subject}"
        email_body = (
            f"You have received a new contact form submission on Rangam Saradha Silks.\n\n"
            f"--------------------------------------------------\n"
            f"Name: {contact_message.name}\n"
            f"Email Address: {contact_message.email}\n"
            f"{phone_line}"
            f"Subject: {contact_message.subject}\n"
            f"Message:\n{contact_message.message}\n"
            f"--------------------------------------------------\n"
            f"Date & Time of submission: {formatted_time}\n"
        )
        
        contact_info_obj = ContactInfo.objects.first()
        recipient_email = getattr(contact_info_obj, 'email', None) or "rangamsaradhasilks@gmail.com"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', recipient_email)

        try:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=from_email,
                recipient_list=[recipient_email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error sending contact form email: {str(e)}")

        return Response(
            {
                "success": True,
                "message": "Thank you for contacting us. We will get back to you shortly.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

def faq_view(request):
    faqs = FAQ.objects.filter(is_active=True).order_by('display_order')
    return render(request, 'home/faq.html', {'faqs': faqs})

def contact_view(request):
    contact_info = ContactInfo.objects.first()
    if not contact_info:
        contact_info = ContactInfo.objects.create()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not name or not email or not subject or not message:
            messages.error(request, "Please fill in all required fields (Name, Email, Subject, Message).")
            return redirect('home:contact')

        contact_msg = ContactMessage.objects.create(
            name=name,
            email=email,
            phone_number=phone_number,
            subject=subject,
            message=message
        )

        formatted_time = contact_msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        phone_line = f"Phone Number: {contact_msg.phone_number}\n" if contact_msg.phone_number else ""
        email_subject = f"New Contact Form Submission - {contact_msg.subject}"
        email_body = (
            f"You have received a new contact form submission on Rangam Saradha Silks.\n\n"
            f"--------------------------------------------------\n"
            f"Name: {contact_msg.name}\n"
            f"Email Address: {contact_msg.email}\n"
            f"{phone_line}"
            f"Subject: {contact_msg.subject}\n"
            f"Message:\n{contact_msg.message}\n"
            f"--------------------------------------------------\n"
            f"Date & Time of submission: {formatted_time}\n"
        )
        recipient_email = getattr(contact_info, 'email', None) or "rangamsaradhasilks@gmail.com"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', recipient_email)

        try:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=from_email,
                recipient_list=[recipient_email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error sending contact form email: {str(e)}")

        messages.success(request, "Thank you for contacting us! We have received your message and will get back to you shortly.")
        return redirect('home:contact')
        
    context = {
        'contact_info': contact_info,
        'subject_list': contact_info.get_subject_list(),
    }
    return render(request, 'home/contact.html', context)

def index(request):
    setting = WebsiteSetting.objects.first()
    hero_mode = getattr(setting, 'hero_display_mode', 'AUTO')

    sliders = HeroSlider.objects.filter(is_active=True).order_by('display_order')
    banners = OfferBanner.objects.filter(is_active=True).order_by('display_order')

    # Mutually exclusive: Show either Hero Slider OR Offer Banner, never both
    if hero_mode == 'HERO_SLIDER':
        show_hero_slider = bool(sliders.exists())
        show_offer_banner = False
    elif hero_mode == 'OFFER_BANNER':
        show_hero_slider = False
        show_offer_banner = bool(banners.exists())
    else:  # AUTO
        if sliders.exists():
            show_hero_slider = True
            show_offer_banner = False
        elif banners.exists():
            show_hero_slider = False
            show_offer_banner = True
        else:
            show_hero_slider = False
            show_offer_banner = False

    categories = Category.objects.filter(is_active=True).order_by('display_order')[:16]
    budget_ranges = BudgetRange.objects.filter(is_active=True).order_by('display_order')
    
    # Dynamic Homepage Product Sections (only in-stock products with Priority SKU Prefixes applied)
    priority_prefixes = setting.get_priority_sku_prefixes() if setting else []
    sku_priority_filter = Q()
    for p in priority_prefixes:
        clean_p = p.strip()
        if clean_p:
            sku_priority_filter |= Q(sku__istartswith=clean_p) | Q(sku__icontains=clean_p)

    curated_condition = Q(is_featured=True) | Q(is_new_arrival=True)
    if priority_prefixes:
        curated_condition |= sku_priority_filter

    curated_qs = Product.objects.filter(is_active=True, stock__gt=0).filter(curated_condition).distinct().prefetch_related('images', 'categories')
    if curated_qs.count() < 4:
        curated_qs = Product.objects.filter(is_active=True, stock__gt=0).prefetch_related('images', 'categories')
    featured_products = apply_sku_priority_and_sorting(curated_qs, site_settings=setting)[:12]

    trending_qs = Product.objects.filter(is_active=True, stock__gt=0, is_trending=True).prefetch_related('images', 'categories')
    trending_products = apply_sku_priority_and_sorting(trending_qs, site_settings=setting)[:4]

    new_arrivals_condition = Q(is_new_arrival=True)
    if priority_prefixes:
        new_arrivals_condition |= sku_priority_filter
    new_arrivals_qs = Product.objects.filter(is_active=True, stock__gt=0).filter(new_arrivals_condition).distinct().prefetch_related('images', 'categories')
    new_arrivals = apply_sku_priority_and_sorting(new_arrivals_qs, site_settings=setting)[:12]

    best_sellers_qs = Product.objects.filter(is_active=True, stock__gt=0, is_best_seller=True).prefetch_related('images', 'categories')
    best_sellers = apply_sku_priority_and_sorting(best_sellers_qs, site_settings=setting)[:12]

    today_deals_qs = Product.objects.filter(is_active=True, stock__gt=0, is_today_deal=True).prefetch_related('images', 'categories')
    if not today_deals_qs.exists():
        today_deals_qs = Product.objects.filter(is_active=True, stock__gt=0, discount_percentage__gt=0).prefetch_related('images', 'categories')
    today_deals = apply_sku_priority_and_sorting(today_deals_qs, site_settings=setting)[:12]
    
    # Why Choose Us, Fabric Curations
    why_choose_us = WhyChooseUs.objects.filter(is_active=True).order_by('display_order')
    fabric_curations = FabricCuration.objects.filter(is_active=True).order_by('display_order')
    
    # Testimonials
    testimonials = Testimonial.objects.filter(is_active=True)[:5]
    
    # Instagram gallery
    insta_posts = InstagramPost.objects.filter(is_active=True).order_by('display_order')[:6]
    
    # FAQ list for homepage
    faqs = FAQ.objects.filter(is_active=True)[:4]

    # Recently viewed products placeholder (fetched from cookie/session)
    recent_ids = request.session.get('recently_viewed', [])
    recently_viewed = Product.objects.filter(id__in=recent_ids, is_active=True, stock__gt=0).prefetch_related('images')[:4]

    context = {
        'sliders': sliders,
        'banners': banners,
        'show_hero_slider': show_hero_slider,
        'show_offer_banner': show_offer_banner,
        'categories': categories,
        'budget_ranges': budget_ranges,
        'featured_products': featured_products,
        'trending_products': trending_products,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
        'today_deals': today_deals,
        'why_choose_us': why_choose_us,
        'fabric_curations': fabric_curations,
        'testimonials': testimonials,
        'insta_posts': insta_posts,
        'faqs': faqs,
        'recently_viewed': recently_viewed,
    }
    return render(request, 'home/index.html', context)

DEFAULT_CMS_PAGES = {
    'privacy-policy': {
        'title': 'Privacy Policy',
        'content': '<h2>Privacy Policy</h2><p>At Rangam Saradha Silks, we value your trust and are committed to protecting your personal information.</p><h4>1. Information Collection</h4><p>We collect essential information required to process your orders, such as your name, shipping address, email address, and phone number.</p><h4>2. Data Usage</h4><p>Your data is strictly used to fulfill orders, process payments, and improve your shopping experience.</p><h4>3. Security</h4><p>We implement robust security measures to protect your personal details against unauthorized access.</p>'
    },
    'terms-conditions': {
        'title': 'Terms & Conditions',
        'content': '<h2>Terms & Conditions</h2><p>Welcome to Rangam Saradha Silks. By accessing and using our website, you agree to comply with our terms of service.</p><h4>1. Product Authenticity</h4><p>All our silk sarees are 100% genuine and sourced directly from authentic master weavers.</p><h4>2. Pricing and Payments</h4><p>All prices are listed in INR. Prices and availability are subject to change without prior notice.</p><h4>3. Intellectual Property</h4><p>All images, content, and branding are the property of Rangam Saradha Silks.</p>'
    },
    'refund-policy': {
        'title': 'Refund & Return Policy',
        'content': '<h2>Refund & Return Policy</h2><p>At Rangam Saradha Silks, we strive to ensure complete customer satisfaction with every handcrafted saree. Each saree undergoes multi-step quality inspection before being securely packaged and dispatched.</p><div class="alert alert-warning my-4 p-3 rounded-3" style="background-color: #fff9e6; border: 1px solid #e0c283;"><h5 class="fw-bold mb-2 text-dark"><i class="bi bi-camera-video-fill text-warning me-2"></i>Mandatory 360&deg; Unboxing Video Proof Policy</h5><p class="mb-2 fs-7 text-dark">To safeguard authentic customer claims and process any return, exchange, or transit damage request, a <strong>continuous uncut parcel opening video</strong> is strictly mandatory.</p><ul class="mb-0 fs-7 ps-3 text-dark"><li>The video must clearly capture the intact, sealed package and shipping label before cutting open.</li><li>The recording must be in a single continuous take with no pauses, cuts, or edits.</li><li>Unfold and display the saree, blouse piece, zari borders, and tags on camera.</li><li>Any defect, missing item, or transit damage must be shown clearly in the video and reported to us within 24 hours of delivery.</li></ul></div><h4>1. Returns & Exchanges Window</h4><p>Eligible for return or exchange within 7 days of delivery. For transit damage or manufacturing defects, video proof must be reported within 24 hours of receipt.</p><h4>2. Item Condition</h4><p>Items must be unworn, unpleated, with original Silk Mark, security tags, and packaging intact.</p><h4>3. Refund Process</h4><p>Once received and quality-verified at our facility, a 100% refund will be credited back to your original payment method within 5 to 7 business days.</p>'
    },
    'shipping-policy': {
        'title': 'Shipping & Delivery Policy',
        'content': '<h2>Shipping & Delivery Policy</h2><p>We provide fast and reliable doorstep delivery across India and internationally.</p><h4>1. Delivery Timelines</h4><p>Orders are dispatched within 24-48 hours. Domestic deliveries typically take 3-6 business days.</p><h4>2. Order Tracking</h4><p>Once dispatched, a tracking ID will be sent to your registered email.</p>'
    },
    'about-us': {
        'title': 'About Our Brand',
        'content': '<p class="lead">Rangam Saradha Silks brings you the finest handcrafted silk sarees embodying rich Indian heritage, timeless elegance, and exquisite craftsmanship.</p><hr class="my-5" style="border-color: var(--border-color);"><p>Each saree in our collection is woven with dedication by artisan weavers using pure silk and genuine zari.</p>'
    }
}

def cms_page_detail(request, slug):
    try:
        page = CMSPage.objects.get(slug=slug)
    except CMSPage.DoesNotExist:
        if slug in DEFAULT_CMS_PAGES:
            page = CMSPage.objects.create(
                slug=slug,
                title=DEFAULT_CMS_PAGES[slug]['title'],
                content=DEFAULT_CMS_PAGES[slug]['content']
            )
        else:
            from django.http import Http404
            raise Http404("Page not found")
            
    context = {'page': page}
    
    if slug == 'about-us':
        # Split content by the horizontal rule separator we seeded
        parts = page.content.split('<hr class="my-5" style="border-color: var(--border-color);">')
        if len(parts) >= 2:
            context['about_section_1'] = parts[0]
            context['about_section_2'] = parts[1]
        else:
            context['about_section_1'] = page.content
            context['about_section_2'] = ""
            
    return render(request, 'home/cms_page.html', context)

def debug_db_view(request):
    if request.GET.get('key') != 'saradha123':
        from django.http import HttpResponse
        return HttpResponse("Unauthorized", status=401)
        
    from django.core.management import call_command
    from django.http import HttpResponse
    
    action = request.GET.get('action')
    log = ""
    if action == 'seed':
        try:
            call_command('loaddata', 'db_seed.json')
            log = "Database seeded successfully!"
        except Exception as e:
            log = f"Failed to seed: {str(e)}"
            
    pages = list(CMSPage.objects.values('id', 'title', 'slug'))
    categories = list(Category.objects.values('id', 'name', 'slug'))
    products = list(Product.objects.values('id', 'name', 'slug'))
    
    html = f"""
    <html>
    <body>
        <h1>Debug Database Dashboard</h1>
        <p><strong>Status:</strong> {log}</p>
        <form method="GET">
            <input type="hidden" name="key" value="saradha123">
            <button type="submit" name="action" value="seed">Run loaddata db_seed.json</button>
        </form>
        
        <h2>CMS Pages ({len(pages)})</h2>
        <pre>{pages}</pre>
        
        <h2>Categories ({len(categories)})</h2>
        <pre>{categories}</pre>
        
        <h2>Products ({len(products)})</h2>
        <pre>{products}</pre>
    </body>
    </html>
    """
    return HttpResponse(html)


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /shop/cart/",
        "Disallow: /shop/checkout/",
        "Disallow: /shop/order/",
        "Disallow: /shop/booking/",
        "Disallow: /shop/coupon/",
        "Disallow: /shop/compare/",
        "Disallow: /shop/wishlist/",
        "Disallow: /api/",
        "Disallow: /debug-db/",
        "Allow: /",
        "",
        "Sitemap: https://rangamsaradhasilks.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


@require_POST
def popup_book_call_api(request):
    """
    AJAX endpoint to book a saree consultation call directly from the promotional popup.
    """
    import json
    import datetime
    import uuid
    from decimal import Decimal
    from django.db import transaction
    from django.http import JsonResponse
    from shop.models import CallBooking, CallSlot
    from shop.views import parse_slot_start_time
    from .models import WebsiteSetting
    
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'login_required': True,
                'message': 'Please log in to your account to book a video call.'
            }, status=401)

        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        full_name = data.get('full_name', '').strip()
        phone_number = data.get('phone_number', '').strip()
        booking_date_str = data.get('booking_date', '').strip()
        time_slot = data.get('time_slot', '').strip()
        saree_preference = data.get('saree_preference', '').strip()
        notes = data.get('notes', '').strip()
        email = data.get('email', '').strip()

        if not full_name:
            return JsonResponse({'success': False, 'message': 'Please enter your name.'}, status=400)
        if not phone_number:
            return JsonResponse({'success': False, 'message': 'Please enter your phone number.'}, status=400)
        if not booking_date_str:
            return JsonResponse({'success': False, 'message': 'Please select a preferred date.'}, status=400)
        if not time_slot:
            return JsonResponse({'success': False, 'message': 'Please choose a preferred time slot.'}, status=400)

        # Validate time slot
        valid_slots = [choice[0] for choice in CallBooking.TIME_SLOT_CHOICES]
        if time_slot not in valid_slots:
            return JsonResponse({'success': False, 'message': 'Please select a valid time slot.'}, status=400)

        # Validate booking date
        try:
            booking_date = datetime.datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format.'}, status=400)

        now_local = timezone.localtime()
        today = now_local.date()
        if booking_date < today:
            return JsonResponse({'success': False, 'message': 'Please select today or a future date.'}, status=400)
        elif booking_date == today:
            slot_start = parse_slot_start_time(time_slot)
            if slot_start and slot_start <= now_local.time():
                return JsonResponse({'success': False, 'message': 'This time slot has already passed for today. Please select an upcoming slot.'}, status=400)

        # Duplicate protection (same phone, date, slot within 5 mins)
        recent_cutoff = timezone.now() - datetime.timedelta(minutes=5)
        existing_booking = CallBooking.objects.filter(
            phone_number=phone_number,
            booking_date=booking_date,
            time_slot=time_slot,
            created_at__gte=recent_cutoff
        ).first()

        if existing_booking:
            return JsonResponse({
                'success': True,
                'booking_ref': existing_booking.booking_reference,
                'booking_reference': existing_booking.booking_reference,
                'message': f"We have already received your booking scheduled for {booking_date} at {time_slot} (Ref: #{existing_booking.booking_reference})."
            })

        payment_method = (data.get('payment_method') or 'UPI').strip().upper()
        if payment_method not in ['UPI', 'CARD', 'NETBANKING', 'ONLINE']:
            payment_method = 'UPI'

        settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
        call_booking_fee = getattr(settings_obj, 'call_booking_fee', Decimal('50.00')) or Decimal('50.00')
        txn_ref = f"TXN-CALL-{uuid.uuid4().hex[:8].upper()}"

        # Atomic creation with slot availability verification
        with transaction.atomic():
            # 1. Check if owner blocked slot
            is_blocked = CallSlot.objects.filter(date=booking_date, time_slot=time_slot).filter(
                Q(blocked_by_owner=True) | Q(status='BLOCKED')
            ).exists()
            if is_blocked:
                return JsonResponse({
                    'success': False,
                    'message': f"The time slot '{time_slot}' on {booking_date.strftime('%b %d, %Y')} is unavailable. Please choose another slot."
                }, status=400)

            # 2. Check if ANY customer has already booked this slot
            is_already_booked = CallBooking.objects.filter(
                booking_date=booking_date,
                time_slot=time_slot,
                status__in=['CONFIRMED', 'COMPLETED']
            ).select_for_update().exists()

            if is_already_booked:
                return JsonResponse({
                    'success': False,
                    'message': f"The time slot '{time_slot}' on {booking_date.strftime('%b %d, %Y')} has already been booked. Please choose another time slot."
                }, status=400)

            booking = CallBooking.objects.create(
                product=None,
                saree_preference=saree_preference or "General Saree Selection Consultation",
                user=request.user,
                full_name=full_name,
                email=request.user.email or email or f"call_{phone_number[-6:]}@rangamsaradhasilk.com",
                phone_number=phone_number,
                booking_date=booking_date,
                time_slot=time_slot,
                notes=notes,
                fee_amount=call_booking_fee,
                payment_status='PAID',
                payment_method=payment_method,
                payment_reference=txn_ref,
                status='CONFIRMED',
            )

            CallSlot.objects.update_or_create(
                date=booking_date,
                time_slot=time_slot,
                defaults={'status': 'BOOKED'}
            )

        # Try email notification
        try:
            from shop.views import send_booking_notification_email
            send_booking_notification_email(booking)
        except Exception as e:
            logger.warning(f"Could not send booking email for popup booking #{booking.booking_reference}: {e}")

        formatted_date = booking_date.strftime('%b %d, %Y')
        return JsonResponse({
            'success': True,
            'booking_ref': booking.booking_reference,
            'booking_reference': booking.booking_reference,
            'fee_amount': float(booking.fee_amount),
            'payment_status': booking.payment_status,
            'payment_method': booking.payment_method,
            'payment_reference': booking.payment_reference,
            'message': f"🎉 Thank you, {full_name}! Your saree selection call is confirmed for {formatted_date} at {time_slot} (Fee: ₹{booking.fee_amount:.0f} Paid)."
        })
    except Exception as e:
        logger.error(f"Error in popup_book_call_api: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred. Please try again.'}, status=500)


