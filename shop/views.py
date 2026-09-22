from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.decorators import customer_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
import datetime
import uuid
import logging
import json
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import Category, Product, ProductImage, Review, Coupon, Cart, CartItem, Order, OrderItem, CallBooking, CallSlot
from accounts.models import Address
from home.models import WebsiteSetting
from .pricing import calculate_order_pricing
from .email_service import send_owner_order_notification_email
from .razorpay_service import create_razorpay_order, verify_payment_signature

logger = logging.getLogger(__name__)

# Cart Helper
def _get_or_create_cart(request):
    if request.user.is_authenticated and not request.user.is_staff:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart


def categories_list(request):
    """
    Dedicated Categories landing page displaying all active saree categories.
    """
    from django.db.models import Count
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__is_active=True, products__stock__gt=0))
    ).order_by('display_order')
    
    context = {
        'categories': categories,
    }
    return render(request, 'shop/categories.html', context)

# Stop words / generic words for saree shopping
SEARCH_STOP_WORDS = {
    'saree', 'sarees', 'sari', 'saris', 'collection', 'wear', 'for', 'in',
    'and', 'the', 'of', 'with', 'a', 'an', 'shop', 'all', 'buy', 'online',
    'pure', 'authentic', 'traditional'
}

# Domain-specific synonym mappings (weaves, fabrics, occasions)
SEARCH_SYNONYMS = {
    'banaras': ['banaras', 'banarasi', 'benarasi', 'benaras'],
    'banarasi': ['banaras', 'banarasi', 'benarasi', 'benaras'],
    'benarasi': ['banaras', 'banarasi', 'benarasi', 'benaras'],
    'benaras': ['banaras', 'banarasi', 'benarasi', 'benaras'],

    'kanchi': ['kanchi', 'kanchipuram', 'kanjivaram', 'kanjeevaram'],
    'kanchipuram': ['kanchi', 'kanchipuram', 'kanjivaram', 'kanjeevaram'],
    'kanjivaram': ['kanchi', 'kanchipuram', 'kanjivaram', 'kanjeevaram'],
    'kanjeevaram': ['kanchi', 'kanchipuram', 'kanjivaram', 'kanjeevaram'],

    'silk': ['silk', 'silks', 'pattu'],
    'silks': ['silk', 'silks', 'pattu'],
    'pattu': ['silk', 'silks', 'pattu'],

    'cotton': ['cotton', 'cottons', 'suti'],
    'cottons': ['cotton', 'cottons', 'suti'],

    'bridal': ['bridal', 'wedding', 'bride', 'marriage', 'vivah', 'trousseau'],
    'wedding': ['bridal', 'wedding', 'bride', 'marriage', 'vivah', 'trousseau'],
    'bride': ['bridal', 'wedding', 'bride', 'marriage', 'vivah'],
    'marriage': ['bridal', 'wedding', 'bride', 'marriage', 'vivah'],

    'party': ['party', 'partywear', 'party wear'],
    'partywear': ['party', 'party wear', 'partywear'],

    'handloom': ['handloom', 'handcrafted', 'handwoven', 'hand woven'],

    'chanderi': ['chanderi'],
    'tussar': ['tussar', 'tusser', 'tassar'],
    'paithani': ['paithani'],
    'organza': ['organza'],
    'georgette': ['georgette'],
    'chiffon': ['chiffon'],
    'crepe': ['crepe'],
    'bandhani': ['bandhani', 'bandhej'],
    'patola': ['patola'],
    'mysore': ['mysore'],
    'uppada': ['uppada'],
    'gadwal': ['gadwal'],
    'pochampally': ['pochampally', 'ikkat', 'ikat'],
    'dharmavaram': ['dharmavaram'],
    'zari': ['zari', 'jari', 'brocade', 'gold zari', 'silver zari'],
    'brocade': ['brocade', 'zari'],
}

SEARCH_PRIMARY_WEAVES = {
    'banaras', 'banarasi', 'benarasi', 'benaras',
    'kanchi', 'kanchipuram', 'kanjivaram', 'kanjeevaram',
    'chanderi', 'paithani', 'patola', 'bandhani', 'bandhej',
    'tussar', 'tusser', 'organza', 'georgette', 'cotton', 'linen'
}

def _build_search_term_q(term):
    """Matches a single keyword across all relevant product fields."""
    return (
        Q(name__icontains=term) |
        Q(categories__name__icontains=term) |
        Q(categories__slug__icontains=term) |
        Q(description__icontains=term) |
        Q(short_description__icontains=term) |
        Q(fabric__icontains=term) |
        Q(material__icontains=term) |
        Q(tags__icontains=term) |
        Q(sku__icontains=term) |
        Q(color__icontains=term) |
        Q(occasion__icontains=term) |
        Q(zari_type__icontains=term) |
        Q(meta_keywords__icontains=term) |
        Q(meta_title__icontains=term)
    )

def filter_products_by_search(queryset, raw_query):
    query_str = (raw_query or '').strip()
    if not query_str:
        return queryset

    # Check for direct exact SKU match first
    sku_match = queryset.filter(sku__iexact=query_str).distinct()
    if sku_match.exists():
        return sku_match

    import re
    # Tokenize input into alphanumeric words
    tokens = [t.lower() for t in re.findall(r'[\w\d]+', query_str)]
    if not tokens:
        return queryset.none()

    # Content tokens excluding generic words
    content_tokens = [t for t in tokens if t not in SEARCH_STOP_WORDS]
    if not content_tokens:
        content_tokens = tokens

    # Strategy 1: Multi-term intersection (AND logic across all search concepts)
    # E.g., "silk saree banaras" -> matches products that satisfy "silk" AND "banaras"
    and_q = Q()
    for token in content_tokens:
        variants = SEARCH_SYNONYMS.get(token, [token])
        token_q = Q()
        for v in variants:
            token_q |= _build_search_term_q(v)
        and_q &= token_q

    and_matches = queryset.filter(and_q).distinct()
    if and_matches.exists():
        return and_matches

    # Strategy 2: If primary weave keyword is specified, filter strictly on that weave
    weave_tokens = [t for t in content_tokens if t in SEARCH_PRIMARY_WEAVES]
    if weave_tokens:
        weave_q = Q()
        for wt in weave_tokens:
            for v in SEARCH_SYNONYMS.get(wt, [wt]):
                weave_q |= _build_search_term_q(v)
        weave_matches = queryset.filter(weave_q).distinct()
        if weave_matches.exists():
            return weave_matches

    # Strategy 3: Fallback to OR across content tokens
    or_q = Q()
    for token in content_tokens:
        variants = SEARCH_SYNONYMS.get(token, [token])
        for v in variants:
            or_q |= _build_search_term_q(v)

    return queryset.filter(or_q).distinct()


def catalog(request, category_slug=None):
    products = Product.objects.filter(is_active=True, stock__gt=0).prefetch_related('images', 'categories')
    
    # SKU Filter
    sku_param = request.GET.get('sku', '').strip()
    if sku_param:
        products = products.filter(sku__icontains=sku_param)

    # Query / Search (Smart multi-keyword + synonym search)
    query = request.GET.get('q')
    if query:
        products = filter_products_by_search(products, query)
        
    # Filters
    category_param = request.GET.get('category') or category_slug
    active_category = None
    if category_param:
        if isinstance(category_param, str) and category_param.isdigit():
            products = products.filter(categories__id=category_param)
            active_category = Category.objects.filter(id=category_param, is_active=True).first()
        else:
            cat_obj = Category.objects.filter(slug=category_param, is_active=True).first()
            if not cat_obj and category_param == 'bridal':
                cat_obj = Category.objects.filter(slug='bridal-collection', is_active=True).first()
            if cat_obj:
                products = products.filter(categories=cat_obj)
                active_category = cat_obj
            else:
                products = products.filter(categories__slug=category_param)
        
    color = request.GET.get('color')
    if color:
        products = products.filter(color__iexact=color)
        
    fabric = request.GET.get('fabric')
    if fabric:
        products = products.filter(
            Q(fabric__icontains=fabric) |
            Q(material__icontains=fabric) |
            Q(name__icontains=fabric) |
            Q(categories__name__icontains=fabric) |
            Q(tags__icontains=fabric)
        ).distinct()

    occasion = request.GET.get('occasion')
    if occasion:
        products = products.filter(occasion__iexact=occasion)
        
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(offer_price__gte=min_price)
    if max_price:
        products = products.filter(offer_price__lte=max_price)
        
    discount = request.GET.get('discount')
    if discount == 'yes':
        products = products.filter(discount_percentage__gt=0)
        
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by == 'price_low':
        products = products.order_by('offer_price')
    elif sort_by == 'price_high':
        products = products.order_by('-offer_price')
    elif sort_by == 'popular':
        products = products.order_by('-is_trending')
    else:
        # Default: newest arrivals
        products = products.order_by('-created_at')

    # Categories and filters for Sidebar UI
    categories = Category.objects.filter(is_active=True)
    
    # Get distinct attribute values for filters
    colors = Product.objects.filter(is_active=True, stock__gt=0).values_list('color', flat=True).distinct()
    fabrics = Product.objects.filter(is_active=True, stock__gt=0).values_list('fabric', flat=True).distinct()
    occasions = Product.objects.filter(is_active=True, stock__gt=0).values_list('occasion', flat=True).distinct()
    
    # Clean filters (omit nulls/blanks)
    colors = [c for c in colors if c]
    fabrics = [f for f in fabrics if f]
    occasions = [o for o in occasions if o]

    # Determine if any filter / query parameter is active in URL
    has_filters = bool(
        category_param or 
        any(v for v in request.GET.values() if v and str(v).strip())
    )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Determine maximum and minimum saree price all over the website
    from django.db.models import Max, Min
    price_stats = Product.objects.filter(is_active=True, stock__gt=0).aggregate(
        max_offer=Max('offer_price'),
        max_regular=Max('price'),
        min_offer=Min('offer_price'),
        min_regular=Min('price')
    )
    
    valid_max_prices = [p for p in [price_stats['max_offer'], price_stats['max_regular']] if p is not None]
    valid_min_prices = [p for p in [price_stats['min_offer'], price_stats['min_regular']] if p is not None]

    max_catalog_price = int(max(valid_max_prices)) if valid_max_prices else 100000
    min_catalog_price = int(min(valid_min_prices)) if valid_min_prices else 0

    context = {
        'products': page_obj,
        'categories': categories,
        'colors': colors,
        'fabrics': fabrics,
        'occasions': occasions,
        'current_filters': request.GET,
        'category_param': category_param,
        'has_filters': has_filters,
        'active_category': active_category,
        'min_catalog_price': min_catalog_price,
        'max_catalog_price': max_catalog_price,
    }
    return render(request, 'shop/catalog.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product.objects.prefetch_related('images', 'categories', 'reviews__user'), slug=slug, is_active=True, stock__gt=0)
    related_products = Product.objects.filter(is_active=True, stock__gt=0, categories__in=product.categories.all()).exclude(id=product.id).distinct()[:4]
    
    # Store in session for recently viewed list
    recent = request.session.get('recently_viewed', [])
    if product.id in recent:
        recent.remove(product.id)
    recent.insert(0, product.id)
    request.session['recently_viewed'] = recent[:10] # limit to last 10
    
    # Approved reviews list
    reviews = product.reviews.filter(is_approved=True)
    rating_avg = 0
    if reviews.exists():
        rating_avg = sum(r.rating for r in reviews) / reviews.count()

    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'rating_avg': rating_avg,
    }
    return render(request, 'shop/detail.html', context)

def cart_detail(request):
    cart = _get_or_create_cart(request)
    cart = Cart.objects.prefetch_related('items__product__images', 'items__product__categories').get(id=cart.id)
    
    # Automatically remove any items that became out of stock or inactive from website
    out_of_stock_items = [item for item in cart.items.all() if not item.product or not item.product.is_active or item.product.stock <= 0]
    if out_of_stock_items:
        removed_names = []
        for item in out_of_stock_items:
            if item.product:
                removed_names.append(item.product.name)
            item.delete()
        if removed_names:
            messages.warning(request, f"The following item(s) became out of stock and were removed from your cart: {', '.join(removed_names)}")
        cart = Cart.objects.prefetch_related('items__product__images', 'items__product__categories').get(id=cart.id)
        
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    
    # Check for coupon in session
    coupon_code = request.session.get('coupon_code')
    coupon = None
    discount = Decimal('0.00')
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            if coupon.is_valid(subtotal, cart=cart):
                discount = coupon.calculate_discount(subtotal, cart=cart)
            else:
                del request.session['coupon_code']
                messages.warning(request, "Coupon became invalid for your current cart items.")
        except Coupon.DoesNotExist:
            del request.session['coupon_code']
            
    pricing = calculate_order_pricing(subtotal, discount=discount, payment_method='ONLINE', settings_obj=settings_obj)

    context = {
        'cart': cart,
        'subtotal': pricing['subtotal'],
        'coupon': coupon,
        'discount': pricing['discount'],
        'tax': pricing['tax_amount'],
        'shipping': pricing['shipping'],
        'order_amount_before_cod': pricing['order_amount_before_cod'],
        'is_cod_eligible': pricing['is_cod_eligible'],
        'cod_is_free': pricing['cod_is_free'],
        'cod_free_threshold': pricing['cod_free_threshold'],
        'cod_max_limit': pricing['cod_max_limit'],
        'standard_cod_fee': pricing['standard_cod_fee'],
        'grand_total': pricing['grand_total'],
        'site_settings': settings_obj,
    }
    return render(request, 'shop/cart.html', context)

def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True, stock__gt=0)
    quantity = int(request.POST.get('quantity', 1))
    buy_now = request.POST.get('buy_now') == 'true'
    
    cart = _get_or_create_cart(request)
    cart_item = CartItem.objects.filter(cart=cart, product=product).first()
    current_in_cart = cart_item.quantity if cart_item else 0
    
    if product.stock < (current_in_cart + quantity):
        messages.error(request, f"Cannot add more items. Only {product.stock} available and you have {current_in_cart} in cart.")
        return redirect(request.META.get('HTTP_REFERER', 'shop:catalog'))
        
    if not cart_item:
        cart_item = CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    else:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f"Added {product.name} to your Cart.")
    if buy_now:
        return redirect('shop:checkout')
    return redirect('shop:cart_detail')

def cart_update(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1

    if quantity <= 0:
        cart_item.delete()
        messages.success(request, "Item removed from Cart.")
    elif cart_item.product.stock < quantity:
        messages.error(request, f"Only {cart_item.product.stock} items available.")
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, "Cart updated.")

    return redirect('shop:cart_detail')


def cart_remove(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.success(request, "Item removed from Cart.")
    return redirect('shop:cart_detail')

def apply_coupon(request):
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop:checkout'
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip()
        cart = _get_or_create_cart(request)
        subtotal = sum(item.get_total_price() for item in cart.items.all())
        
        try:
            coupon = Coupon.objects.get(code__iexact=code, is_active=True)
            today = datetime.date.today()
            if coupon.start_date and coupon.start_date > today:
                messages.error(request, f"Coupon '{code}' is not active yet (starts on {coupon.start_date.strftime('%d-%m-%Y')}).")
            elif coupon.expiry_date and coupon.expiry_date < today:
                messages.error(request, f"Coupon '{code}' has expired.")
            elif coupon.used_count >= coupon.usage_limit:
                messages.error(request, f"Coupon '{code}' usage limit has been reached.")
            elif subtotal < coupon.min_purchase:
                messages.error(request, f"Minimum purchase amount of ₹{coupon.min_purchase:.0f} required to apply this coupon.")
            elif coupon.apply_to in ('CATEGORIES', 'PRODUCTS') and not coupon.get_eligible_items(cart):
                if coupon.apply_to == 'CATEGORIES':
                    messages.error(request, f"Coupon '{code}' applies only to selected categories. None are in your cart.")
                else:
                    messages.error(request, f"Coupon '{code}' applies only to specific products. None are in your cart.")
            elif coupon.is_valid(subtotal, cart=cart):
                request.session['coupon_code'] = coupon.code
                messages.success(request, f"Coupon '{coupon.code}' applied successfully!")
            else:
                messages.error(request, "Coupon could not be applied to your current cart.")
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid coupon code.")
            
    return redirect(next_url)

def remove_coupon(request):
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
        messages.success(request, "Coupon removed.")
    next_url = request.GET.get('next') or request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop:checkout'
    return redirect(next_url)

@customer_required
def checkout(request):
    cart = _get_or_create_cart(request)
    cart = Cart.objects.prefetch_related('items__product__images', 'items__product__categories').get(id=cart.id)
    
    # Automatically remove any items that became out of stock or inactive from website
    out_of_stock_items = [item for item in cart.items.all() if not item.product or not item.product.is_active or item.product.stock <= 0]
    if out_of_stock_items:
        removed_names = []
        for item in out_of_stock_items:
            if item.product:
                removed_names.append(item.product.name)
            item.delete()
        if removed_names:
            messages.warning(request, f"The following item(s) became out of stock and were removed from your cart: {', '.join(removed_names)}")
        return redirect('shop:cart_detail')
        
    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('shop:cart_detail')
        
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    addresses = Address.objects.filter(user=request.user)
    
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    
    # Coupon calculation
    coupon_code = request.session.get('coupon_code')
    coupon = None
    discount = Decimal('0.00')
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            if coupon.is_valid(subtotal, cart=cart):
                discount = coupon.calculate_discount(subtotal, cart=cart)
        except Coupon.DoesNotExist:
            pass
            
    # Pricing evaluation
    pricing = calculate_order_pricing(subtotal, discount=discount, payment_method='COD', settings_obj=settings_obj)
    default_payment = 'COD'

    context = {
        'cart': cart,
        'addresses': addresses,
        'subtotal': pricing['subtotal'],
        'coupon': coupon,
        'discount': pricing['discount'],
        'tax': pricing['tax_amount'],
        'shipping': pricing['shipping'],
        'order_amount_before_cod': pricing['order_amount_before_cod'],
        'is_cod_eligible': pricing['is_cod_eligible'],
        'cod_is_free': pricing['cod_is_free'],
        'cod_free_threshold': pricing['cod_free_threshold'],
        'cod_max_limit': pricing['cod_max_limit'],
        'standard_cod_fee': pricing['standard_cod_fee'],
        'cod_charge': pricing['cod_charge'],
        'default_payment_method': default_payment,
        'grand_total': pricing['grand_total'],
        'site_settings': settings_obj,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', '') or os.environ.get('RAZORPAY_KEY_ID', ''),
    }
    return render(request, 'shop/checkout.html', context)

@customer_required
def order_create(request):
    from django.db import transaction
    if request.method == 'POST':
        cart = _get_or_create_cart(request)
        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('shop:cart_detail')
            
        address_id = request.POST.get('address_id')
        if not address_id:
            messages.error(request, "Please select a delivery address.")
            return redirect('shop:checkout')
            
        address = get_object_or_404(Address, id=address_id, user=request.user)
        payment_method = request.POST.get('payment_method', 'COD').upper()
        if payment_method not in ['COD', 'ONLINE']:
            payment_method = 'ONLINE'
        
        try:
            with transaction.atomic():
                # Lock products using select_for_update to avoid race conditions/overselling
                cart_items = list(cart.items.all())
                product_ids = [item.product_id for item in cart_items]
                
                locked_products = {
                    p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
                }
                
                # Validate stock for all items
                for item in cart_items:
                    product = locked_products.get(item.product_id)
                    if not product or not product.is_active:
                        raise ValueError(f"Product '{item.product.name}' is no longer active.")
                    if product.stock < item.quantity:
                        raise ValueError(f"Product '{product.name}' has insufficient stock. Only {product.stock} left.")
                
                # Calculate pricing directly on the server - NEVER trust frontend amounts
                settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
                subtotal = sum(item.get_total_price() for item in cart_items)
                
                # Coupon
                coupon_code = request.session.get('coupon_code')
                coupon = None
                discount = Decimal('0.00')
                if coupon_code:
                    try:
                        coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                        if coupon.is_valid(subtotal, cart=cart):
                            discount = coupon.calculate_discount(subtotal, cart=cart)
                    except Coupon.DoesNotExist:
                        pass
                        
                pricing = calculate_order_pricing(subtotal, discount=discount, payment_method=payment_method, settings_obj=settings_obj)
                
                # STRICT BACKEND COD SECURITY VALIDATION
                if payment_method == 'COD' and not pricing['is_cod_eligible']:
                    messages.error(request, f"Cash on Delivery is available only for orders below ₹{pricing['cod_max_limit']:.0f}. Please choose Online Payment.")
                    return redirect('shop:checkout')

                tax = pricing['tax_amount']
                shipping = pricing['shipping']
                cod_charge = pricing['cod_charge']
                grand_total = pricing['grand_total']
                final_payment_method = pricing['effective_payment_method']
                
                # Generate Order Number
                order_number = f"RS-{uuid.uuid4().hex[:8].upper()}"
                
                # Create Order
                order = Order.objects.create(
                    user=request.user,
                    order_number=order_number,
                    full_name=address.full_name,
                    phone_number=str(address.phone_number),
                    email=request.user.email,
                    address_line_1=address.address_line_1,
                    address_line_2=address.address_line_2,
                    city=address.city,
                    state=address.state,
                    pincode=address.pincode,
                    landmark=address.landmark,
                    payment_method=final_payment_method,
                    payment_status='PENDING' if final_payment_method == 'COD' else 'PAID',
                    order_status='PENDING',
                    subtotal=pricing['subtotal'],
                    shipping_cost=shipping,
                    tax_amount=tax,
                    cod_charge=cod_charge,
                    discount_amount=pricing['discount'],
                    grand_total=grand_total,
                    coupon_used=coupon
                )
                
                # Move CartItems to OrderItems and decrement stock
                for item in cart_items:
                    product = locked_products.get(item.product_id)
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item.quantity,
                        price=item.get_unit_price_with_tax()
                    )
                    product.stock -= item.quantity
                    product.save()
                    
                # Update Coupon usage
                if coupon:
                    coupon.used_count += 1
                    coupon.save()
                    del request.session['coupon_code']
                    
                # Clear Cart
                cart.items.all().delete()
                
                # Dispatch comprehensive accounting order notification to store owner/admin
                send_owner_order_notification_email(order)
                
                messages.success(request, f"Order #{order_number} placed successfully!")
                return render(request, 'shop/order_success.html', {'order': order, 'site_settings': settings_obj})
                
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('shop:cart_detail')
            
    return redirect('shop:checkout')


@customer_required
@require_POST
def razorpay_create_order(request):
    """
    Authoritatively calculates final order total on the Django backend
    and creates a pending Order along with a Razorpay Order ID.
    Inventory is NOT deducted and cart is NOT cleared until payment verification succeeds.
    """
    cart = _get_or_create_cart(request)
    if not cart.items.exists():
        return JsonResponse({'success': False, 'error': 'Your cart is empty.'}, status=400)

    # Support both JSON payload and standard form-data
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    address_id = data.get('address_id')
    if not address_id:
        return JsonResponse({'success': False, 'error': 'Please select a delivery address.'}, status=400)

    try:
        address = Address.objects.get(id=address_id, user=request.user)
    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Selected address was not found.'}, status=400)

    cart_items = list(cart.items.select_related('product').all())

    # Check product stock and active status
    for item in cart_items:
        product = item.product
        if not product or not product.is_active:
            return JsonResponse({'success': False, 'error': f"Product '{item.product.name if item.product else 'Item'}' is no longer active."}, status=400)
        if product.stock < item.quantity:
            return JsonResponse({'success': False, 'error': f"Product '{product.name}' has insufficient stock. Only {product.stock} left."}, status=400)

    # Authoritative calculation of pricing directly on server - NEVER trust frontend amount
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    subtotal = sum(item.get_total_price() for item in cart_items)

    # Coupon
    coupon_code = request.session.get('coupon_code')
    coupon = None
    discount = Decimal('0.00')
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            if coupon.is_valid(subtotal, cart=cart):
                discount = coupon.calculate_discount(subtotal, cart=cart)
        except Coupon.DoesNotExist:
            pass

    pricing = calculate_order_pricing(subtotal, discount=discount, payment_method='RAZORPAY', settings_obj=settings_obj)
    grand_total = pricing['grand_total']

    # Generate unique Order Number
    order_number = f"RS-{uuid.uuid4().hex[:8].upper()}"

    try:
        rzp_order = create_razorpay_order(
            amount_in_inr=grand_total,
            receipt=order_number,
            notes={
                'order_number': order_number,
                'user_id': str(request.user.id),
                'customer_email': request.user.email,
            }
        )
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}", exc_info=True)
        err_msg = str(e)
        if hasattr(e, 'message'):
            err_msg = e.message
        return JsonResponse({
            'success': False,
            'error': f"Online payment gateway error: {err_msg}"
        }, status=400)

    # Create pending Order record in Django DB
    with transaction.atomic():
        order = Order.objects.create(
            user=request.user,
            order_number=order_number,
            full_name=address.full_name,
            phone_number=str(address.phone_number),
            email=request.user.email,
            address_line_1=address.address_line_1,
            address_line_2=address.address_line_2,
            city=address.city,
            state=address.state,
            pincode=address.pincode,
            landmark=address.landmark,
            payment_method='RAZORPAY',
            payment_status='PENDING',
            order_status='PENDING',
            subtotal=pricing['subtotal'],
            shipping_cost=pricing['shipping'],
            tax_amount=pricing['tax_amount'],
            cod_charge=pricing['cod_charge'],
            discount_amount=pricing['discount'],
            grand_total=grand_total,
            coupon_used=coupon,
            razorpay_order_id=rzp_order['id'],
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.get_unit_price_with_tax()
            )

    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '') or os.environ.get('RAZORPAY_KEY_ID', '')
    if not key_id or 'placeholder' in key_id:
        try:
            from dotenv import load_dotenv
            load_dotenv(settings.BASE_DIR / ".env", override=True)
            key_id = os.environ.get('RAZORPAY_KEY_ID', '')
        except Exception:
            pass

    return JsonResponse({
        'success': True,
        'razorpay_order_id': rzp_order['id'],
        'amount': rzp_order['amount'],  # in paise
        'currency': rzp_order.get('currency', 'INR'),
        'key_id': key_id,
        'order_number': order_number,
        'customer_name': address.full_name,
        'customer_email': request.user.email,
        'customer_phone': str(address.phone_number),
    })


@customer_required
@require_POST
def razorpay_verify_payment(request):
    """
    Verifies Razorpay HMAC signature on Django backend.
    Only after successful verification:
    - Mark payment as PAID
    - Confirm order
    - Save razorpay_payment_id and razorpay_signature
    - Deduct inventory exactly once (idempotent)
    - Increment coupon usage
    - Clear customer's cart
    - Dispatch confirmation emails
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return JsonResponse({'success': False, 'error': 'Missing required payment verification details.'}, status=400)

    # Verify Razorpay signature using official SDK
    is_valid = verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    if not is_valid:
        logger.warning(f"Invalid signature received for Razorpay order {razorpay_order_id}")
        # Update order status to FAILED
        Order.objects.filter(razorpay_order_id=razorpay_order_id, user=request.user).update(payment_status='FAILED')
        return JsonResponse({
            'success': False,
            'error': 'Payment verification failed. Invalid digital signature.'
        }, status=400)

    # Signature is valid! Process order confirmation inside atomic transaction
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            )
        except Order.DoesNotExist:
            logger.error(f"Order with razorpay_order_id={razorpay_order_id} not found for user {request.user.id}")
            return JsonResponse({'success': False, 'error': 'Order not found.'}, status=404)

        # Idempotency check: if already paid, do not decrement inventory again
        if order.payment_status == 'PAID':
            logger.info(f"Order #{order.order_number} already marked as PAID. Skipping duplicate deduction.")
            redirect_url = reverse('shop:order_success', kwargs={'order_number': order.order_number})
            return JsonResponse({'success': True, 'redirect_url': redirect_url, 'order_number': order.order_number})

        # Decrement inventory exactly once
        order_items = list(order.items.select_related('product').all())
        product_ids = [item.product_id for item in order_items if item.product_id]
        locked_products = {p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)}

        for item in order_items:
            if item.product_id and item.product_id in locked_products:
                product = locked_products[item.product_id]
                product.stock = max(0, product.stock - item.quantity)
                product.save()

        # Mark order as PAID and CONFIRMED
        order.payment_status = 'PAID'
        order.order_status = 'CONFIRMED'
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        order.paid_at = timezone.now()
        order.save()

        # Update coupon usage
        if order.coupon_used:
            order.coupon_used.used_count += 1
            order.coupon_used.save()
            if 'coupon_code' in request.session:
                del request.session['coupon_code']

        # Clear customer cart
        cart = _get_or_create_cart(request)
        cart.items.all().delete()

        # Send owner order notification email
        send_owner_order_notification_email(order)

    # Success! Redirect to order success page
    redirect_url = reverse('shop:order_success', kwargs={'order_number': order.order_number})
    messages.success(request, f"Online payment verified! Order #{order.order_number} placed successfully.")
    return JsonResponse({
        'success': True,
        'order_number': order.order_number,
        'redirect_url': redirect_url
    })


@customer_required
@require_POST
def razorpay_payment_failed(request):
    """
    Handles payment cancellation, window closure, or payment gateway failures.
    Does NOT mark order as paid. Does NOT deduct stock. Does NOT delete cart.
    Allows customer to retry safely.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    razorpay_order_id = data.get('razorpay_order_id')
    error_reason = data.get('reason', 'Payment cancelled or dismissed by customer')

    if razorpay_order_id:
        Order.objects.filter(
            razorpay_order_id=razorpay_order_id,
            user=request.user,
            payment_status='PENDING'
        ).update(payment_status='FAILED')
        logger.info(f"Payment marked FAILED for razorpay_order_id={razorpay_order_id}. Reason: {error_reason}")

    return JsonResponse({
        'success': True,
        'message': 'Payment was not completed. Your order has not been confirmed.'
    })


@customer_required
def order_success(request, order_number):
    """Order confirmation and printable invoice page."""
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), order_number=order_number, user=request.user)
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    return render(request, 'shop/order_success.html', {'order': order, 'site_settings': settings_obj})


@customer_required
def order_detail(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), order_number=order_number, user=request.user)
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    return render(request, 'shop/order_detail.html', {'order': order, 'site_settings': settings_obj})

@customer_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True, stock__gt=0)
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 5))
        comment = request.POST.get('comment')
        image = request.FILES.get('image')
        
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment,
            image=image,
            is_approved=True
        )
        messages.success(request, "Your review has been submitted successfully! Thank you for your feedback.")
        
    from django.urls import reverse
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer if referer else reverse('shop:product_detail', args=[product.slug]))


def product_quick_view(request, product_id):
    from django.urls import reverse
    product = get_object_or_404(Product, id=product_id, is_active=True, stock__gt=0)
    images = [img.image.url for img in product.images.all()]
    if not images:
        images = ["https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&q=80&w=800"]
    
    categories = [cat.name for cat in product.categories.all()]
    category = categories[0] if categories else "Silk Saree"
    
    highlights = []
    if product.fabric:
        highlights.append(f"Fabric: {product.fabric}")
    if product.color:
        highlights.append(f"Color: {product.color}")
    if product.material:
        highlights.append(f"Material: {product.material}")
    if product.zari_type and len(highlights) < 6:
        highlights.append(f"Zari: {product.zari_type}")
    for item in product.parsed_specifications:
        if len(highlights) < 6:
            highlights.append(f"{item[0]}: {item[1]}")
            
    in_wishlist = False
    if request.user.is_authenticated and not request.user.is_staff:
        from accounts.models import Wishlist
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    data = {
        'id': product.id,
        'name': product.name,
        'slug': product.slug,
        'sku': product.sku,
        'category': category,
        'current_price': float(product.offer_price),
        'original_price': float(product.price) if product.discount_percentage > 0 else None,
        'discount_percentage': product.discount_percentage,
        'stock': product.stock,
        'stock_status': 'In Stock' if product.stock > 5 else f'Only {product.stock} Left',
        'short_description': product.short_description or (product.description[:200] + '...'),
        'highlights': highlights,
        'images': images,
        'in_wishlist': in_wishlist,
        'detail_url': reverse('shop:product_detail', args=[product.slug]),
        'add_to_cart_url': reverse('shop:cart_add', args=[product.id]),
    }
    return JsonResponse(data)


def compare_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True, stock__gt=0)
    compare_list = request.session.get('compare_list', [])
    
    if product.id not in compare_list:
        compare_list.append(product.id)
        if len(compare_list) > 4:
            compare_list = compare_list[-4:]
        request.session['compare_list'] = compare_list
        request.session.modified = True
        messages.success(request, f"Added {product.name} to comparison list.")
    else:
        messages.info(request, f"{product.name} is already in the comparison list.")
        
    return redirect('shop:compare_page')


def compare_remove(request, product_id):
    compare_list = request.session.get('compare_list', [])
    if product_id in compare_list:
        compare_list.remove(product_id)
        request.session['compare_list'] = compare_list
        request.session.modified = True
        messages.success(request, "Product removed from comparison list.")
    return redirect('shop:compare_page')


def compare_page(request):
    compare_ids = request.session.get('compare_list', [])
    products = Product.objects.filter(id__in=compare_ids, is_active=True, stock__gt=0).prefetch_related('images', 'categories')
    
    # Clean out of stock or inactive products from session compare_list
    valid_ids = [p.id for p in products]
    if len(valid_ids) != len(compare_ids):
        request.session['compare_list'] = [pid for pid in compare_ids if pid in valid_ids]
        request.session.modified = True
    
    # Sort products in the order they were added
    products_dict = {p.id: p for p in products}
    ordered_products = [products_dict[pid] for pid in compare_ids if pid in products_dict]
    
    context = {
        'products': ordered_products,
    }
    return render(request, 'shop/compare.html', context)


def parse_slot_start_time(slot_str):
    """
    Parses start time from a slot string like '10:00 AM - 11:00 AM' or '02:00 PM - 03:00 PM'.
    Returns datetime.time object or None.
    """
    if not slot_str:
        return None
    try:
        start_part = slot_str.split('-')[0].strip()
        return datetime.datetime.strptime(start_part, '%I:%M %p').time()
    except Exception:
        return None


def get_slots_status_for_date(target_date):
    """
    Returns list of dicts for each standard time slot for target_date:
    [
        {
            'time_slot': '10:00 AM - 11:00 AM',
            'status': 'AVAILABLE' | 'BOOKED' | 'BLOCKED' | 'TIME_PASSED',
            'is_selectable': True | False,
            'label': 'Available' | 'Already booked' | 'Owner unavailable' | 'Time passed',
        }, ...
    ]
    """
    now_local = timezone.localtime()
    today = now_local.date()
    current_time = now_local.time()
    is_past_date = target_date < today
    is_today = target_date == today

    # Blocked by owner
    blocked_slots = set(
        CallSlot.objects.filter(date=target_date).filter(
            Q(blocked_by_owner=True) | Q(status='BLOCKED')
        ).values_list('time_slot', flat=True)
    )

    # Booked slots are strictly determined by active confirmed or completed bookings
    booked_slots = set(
        CallBooking.objects.filter(
            booking_date=target_date,
            status__in=['CONFIRMED', 'COMPLETED']
        ).values_list('time_slot', flat=True)
    )

    # Auto-heal any stale CallSlot where status is BOOKED but booking was deleted or cancelled
    CallSlot.objects.filter(
        date=target_date,
        status='BOOKED',
        blocked_by_owner=False
    ).exclude(time_slot__in=booked_slots).update(status='AVAILABLE')

    result = []
    valid_slots = [choice[0] for choice in CallBooking.TIME_SLOT_CHOICES]
    for slot_str in valid_slots:
        slot_start = parse_slot_start_time(slot_str)
        is_slot_passed = False
        if is_past_date:
            is_slot_passed = True
        elif is_today and slot_start and slot_start <= current_time:
            is_slot_passed = True

        if is_slot_passed:
            status = 'TIME_PASSED'
            is_selectable = False
            label = 'Time passed'
        elif slot_str in blocked_slots:
            status = 'BLOCKED'
            is_selectable = False
            label = 'Owner unavailable'
        elif slot_str in booked_slots:
            status = 'BOOKED'
            is_selectable = False
            label = 'Already booked'
        else:
            status = 'AVAILABLE'
            is_selectable = True
            label = 'Available'

        result.append({
            'time_slot': slot_str,
            'status': status,
            'is_selectable': is_selectable,
            'label': label,
        })
    return result


def slot_availability_api(request):
    """
    API endpoint returning time slot status for a given date ?date=YYYY-MM-DD
    """
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'Missing date parameter'}, status=400)

    try:
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    slots_data = get_slots_status_for_date(target_date)
    return JsonResponse({
        'date': date_str,
        'slots': slots_data,
    })


def sku_autocomplete_api(request):
    """
    Fast API endpoint for live SKU auto-suggestions in filters and search.
    Returns matching products with SKU, title, thumbnail, price, and catalog filter query.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})

    matches = Product.objects.filter(
        is_active=True,
        stock__gt=0
    ).filter(
        Q(sku__icontains=q) | Q(name__icontains=q)
    ).prefetch_related('images')[:8]

    results = []
    for p in matches:
        first_img = p.images.first()
        img_url = first_img.image.url if first_img and first_img.image else ''
        price_val = p.offer_price if p.offer_price is not None else p.price
        results.append({
            'sku': p.sku,
            'name': p.name,
            'price': f"{price_val:.2f}" if price_val else "0.00",
            'image': img_url,
            'url': p.get_absolute_url(),
        })

    return JsonResponse({'results': results})


def send_booking_notification_email(booking):
    """
    Sends email confirmation to customer and notification to store admin.
    Fails silently without interrupting booking process if SMTP error occurs.
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'Rangam Saradha Silks <rangamsaradhasilks@gmail.com>'

    # 1. CUSTOMER CONFIRMATION EMAIL
    product_label = booking.product.name if booking.product else (booking.saree_preference or "General Saree Selection")
    fee_display = f"₹{booking.fee_amount:.2f}" if booking.fee_amount else "₹50.00"

    if booking.email and str(booking.email).strip():
        try:
            customer_subject = "Call Booking Confirmed - Rangam Saradha Silks"
            customer_text = (
                f"Dear {booking.full_name},\n\n"
                f"Thank you for booking a call with Rangam Saradha Silks.\n\n"
                f"Your call booking and consultation fee payment have been successfully received.\n\n"
                f"Booking Details:\n\n"
                f"Booking ID: {booking.booking_reference}\n"
                f"Product: {product_label}\n"
                f"Date: {booking.booking_date.strftime('%Y-%m-%d')}\n"
                f"Time Slot: {booking.time_slot}\n"
                f"Consultation Fee Paid: {fee_display} (Status: {booking.payment_status})\n"
                f"Payment Method: {booking.get_payment_method_display()}\n"
                f"Transaction Reference: {booking.payment_reference or 'N/A'}\n"
                f"Phone: {booking.phone_number}\n"
                f"Email: {booking.email}\n\n"
                f"Our team will reach out to you during your selected time slot.\n\n"
                f"Thank you for choosing Rangam Saradha Silks.\n\n"
                f"Regards,\n"
                f"Rangam Saradha Silks\n"
                f"https://rangamsaradhasilks.com/"
            )
            
            customer_html = render_to_string('shop/emails/customer_call_booking_confirmation.html', {'booking': booking})
            
            msg_customer = EmailMultiAlternatives(
                subject=customer_subject,
                body=customer_text,
                from_email=from_email,
                to=[str(booking.email).strip()]
            )
            msg_customer.attach_alternative(customer_html, "text/html")
            msg_customer.send(fail_silently=True)
        except Exception as e:
            logger.error(f"Failed to send customer call booking confirmation email: {str(e)}", exc_info=True)

    # 2. ADMIN / OWNER NOTIFICATION EMAIL
    try:
        owner_subject = f"New Call Booking - {product_label} (Fee: {fee_display} Paid)"
        created_str = booking.created_at.strftime('%Y-%m-%d %H:%M:%S') if booking.created_at else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sku_str = (booking.product.sku if booking.product.sku else str(booking.product.id)) if booking.product else "N/A"
        notes_str = booking.notes if booking.notes else "None"
        if booking.product:
            price_val = booking.product.offer_price if booking.product.offer_price else booking.product.price
            price_str = f"Rs. {price_val:.2f}"
            product_id_val = str(booking.product.id)
        else:
            price_str = "Consultation"
            product_id_val = "N/A"

        owner_text = (
            f"New customer call booking received.\n\n"
            f"Booking ID: {booking.booking_reference}\n\n"
            f"Customer Name: {booking.full_name}\n"
            f"Phone: {booking.phone_number}\n"
            f"Email: {booking.email or 'N/A'}\n\n"
            f"Product: {product_label}\n"
            f"Product ID: {product_id_val}\n"
            f"SKU: {sku_str}\n"
            f"Price: {price_str}\n\n"
            f"Date: {booking.booking_date.strftime('%Y-%m-%d')}\n"
            f"Time Slot: {booking.time_slot}\n\n"
            f"Consultation Fee: {fee_display} (Status: {booking.payment_status})\n"
            f"Payment Method: {booking.get_payment_method_display()}\n"
            f"Transaction ID: {booking.payment_reference or 'N/A'}\n\n"
            f"Message:\n"
            f"{notes_str}\n\n"
            f"Booking Status: {booking.get_status_display()}\n"
            f"Created At: {created_str}\n\n"
            f"Note: Customer has paid the booking fee of {fee_display} for this video consultation."
        )

        owner_html = render_to_string('shop/emails/admin_call_booking_notification.html', {'booking': booking})

        msg_owner = EmailMultiAlternatives(
            subject=owner_subject,
            body=owner_text,
            from_email=from_email,
            to=["rangamsaradhasilks@gmail.com"]
        )
        msg_owner.attach_alternative(owner_html, "text/html")
        msg_owner.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send owner call booking notification email: {str(e)}", exc_info=True)


@login_required(login_url='accounts:login')
def book_call(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True, stock__gt=0)
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    call_booking_fee = getattr(settings_obj, 'call_booking_fee', Decimal('50.00')) or Decimal('50.00')
    
    now_local = timezone.localtime()
    today = now_local.date()
    available_dates = [today + datetime.timedelta(days=i) for i in range(0, 8)]
    valid_time_slots = [choice[0] for choice in CallBooking.TIME_SLOT_CHOICES]

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        booking_date_str = request.POST.get('booking_date', '').strip()
        time_slot = request.POST.get('time_slot', '').strip()
        notes = request.POST.get('notes', '').strip()
        payment_method = request.POST.get('payment_method', 'UPI').strip().upper()
        if payment_method not in ['UPI', 'CARD', 'NETBANKING', 'ONLINE']:
            payment_method = 'UPI'

        errors = []
        if not full_name:
            errors.append("Full Name is required.")
        if not phone_number:
            errors.append("Phone Number is required.")
        if not booking_date_str:
            errors.append("Please select a booking date.")
        if not time_slot or time_slot not in valid_time_slots:
            errors.append("Please select a valid time slot.")

        booking_date = None
        if booking_date_str:
            try:
                booking_date = datetime.datetime.strptime(booking_date_str, '%Y-%m-%d').date()
                if booking_date < today:
                    errors.append("Booking date cannot be in the past.")
                elif booking_date == today and time_slot:
                    slot_start = parse_slot_start_time(time_slot)
                    if slot_start and slot_start <= now_local.time():
                        errors.append("This time slot has already passed for today. Please select an upcoming slot.")
            except ValueError:
                errors.append("Invalid date format.")

        # Backend Verification for Blocked/Booked slots with Transaction locking
        if booking_date and time_slot and time_slot in valid_time_slots and not errors:
            with transaction.atomic():
                # 1. Check if owner blocked slot
                is_blocked = CallSlot.objects.filter(date=booking_date, time_slot=time_slot).filter(
                    Q(blocked_by_owner=True) | Q(status='BLOCKED')
                ).exists()
                if is_blocked:
                    errors.append("This time slot is blocked by the owner. Please select another slot.")

                # 2. Check if already booked
                is_booked = CallBooking.objects.filter(
                    booking_date=booking_date,
                    time_slot=time_slot,
                    status__in=['CONFIRMED', 'COMPLETED']
                ).select_for_update().exists()
                if is_booked:
                    errors.append("This time slot has already been booked. Please select another time slot.")

        if errors:
            for error in errors:
                messages.error(request, error)
            selected_date = booking_date if booking_date else (available_dates[0] if available_dates else today)
            slots_data = get_slots_status_for_date(selected_date)
            return render(request, 'shop/book_call.html', {
                'product': product,
                'available_dates': available_dates,
                'selected_date': selected_date.strftime('%Y-%m-%d'),
                'today': today,
                'slots_data': slots_data,
                'available_slots_count': sum(1 for s in slots_data if s.get('is_selectable')),
                'form_data': request.POST,
                'call_booking_fee': call_booking_fee,
                'site_settings': settings_obj,
            })

        # Duplicate protection check (same product, phone, date, slot in last 5 mins)
        recent_cutoff = timezone.now() - datetime.timedelta(minutes=5)
        existing_booking = CallBooking.objects.filter(
            product=product,
            phone_number=phone_number,
            booking_date=booking_date,
            time_slot=time_slot,
            created_at__gte=recent_cutoff
        ).first()

        if existing_booking:
            return redirect('shop:booking_confirmation', booking_ref=existing_booking.booking_reference)

        txn_ref = f"TXN-CALL-{uuid.uuid4().hex[:8].upper()}"

        with transaction.atomic():
            booking = CallBooking.objects.create(
                product=product,
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                email=email,
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

            # Sync/Update CallSlot status
            CallSlot.objects.update_or_create(
                date=booking_date,
                time_slot=time_slot,
                defaults={
                    'status': 'BOOKED',
                    'notes': f'Booked by {booking.full_name} ({booking.phone_number})'
                }
            )

        try:
            send_booking_notification_email(booking)
        except Exception as e:
            logger.error(f"Error in send_booking_notification_email: {str(e)}", exc_info=True)

        return redirect('shop:booking_confirmation', booking_ref=booking.booking_reference)

    selected_date_str = request.GET.get('booking_date')
    selected_date = available_dates[0] if available_dates else today
    if selected_date_str:
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    slots_data = get_slots_status_for_date(selected_date)

    form_data = {}
    if request.user.is_authenticated:
        phone_val = ''
        if hasattr(request.user, 'phone_number') and request.user.phone_number:
            phone_val = str(request.user.phone_number)
        form_data = {
            'full_name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'phone_number': phone_val,
        }

    return render(request, 'shop/book_call.html', {
        'product': product,
        'available_dates': available_dates,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'today': today,
        'slots_data': slots_data,
        'available_slots_count': sum(1 for s in slots_data if s.get('is_selectable')),
        'form_data': form_data,
        'call_booking_fee': call_booking_fee,
        'site_settings': settings_obj,
    })


def booking_confirmation(request, booking_ref):
    booking = get_object_or_404(CallBooking, booking_reference=booking_ref)
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    return render(request, 'shop/booking_confirmation.html', {
        'booking': booking,
        'site_settings': settings_obj,
    })

