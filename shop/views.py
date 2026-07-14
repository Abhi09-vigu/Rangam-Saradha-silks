from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.decorators import customer_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.utils import timezone
import datetime
import uuid
from decimal import Decimal

from .models import Category, Collection, Product, ProductImage, Review, Coupon, Cart, CartItem, Order, OrderItem
from accounts.models import Address
from home.models import WebsiteSetting

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

def catalog(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images', 'categories')
    
    # Query / Search
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )
        
    # Filters
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(categories__slug=category_slug)
        
    collection_id = request.GET.get('collection')
    if collection_id:
        products = products.filter(collection_id=collection_id)
        
    color = request.GET.get('color')
    if color:
        products = products.filter(color__iexact=color)
        
    fabric = request.GET.get('fabric')
    if fabric:
        products = products.filter(fabric__iexact=fabric)

    occasion = request.GET.get('occasion')
    if occasion:
        products = products.filter(occasion__iexact=occasion)
        
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(offer_price__gte=min_price)
    if max_price:
        products = products.filter(offer_price__lte=max_price)
        
    availability = request.GET.get('stock')
    if availability == 'in_stock':
        products = products.filter(stock__gt=0)
        
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
    collections = Collection.objects.filter(is_active=True)
    
    # Get distinct attribute values for filters
    colors = Product.objects.filter(is_active=True).values_list('color', flat=True).distinct()
    fabrics = Product.objects.filter(is_active=True).values_list('fabric', flat=True).distinct()
    occasions = Product.objects.filter(is_active=True).values_list('occasion', flat=True).distinct()
    
    # Clean filters (omit nulls/blanks)
    colors = [c for c in colors if c]
    fabrics = [f for f in fabrics if f]
    occasions = [o for o in occasions if o]

    context = {
        'products': products,
        'categories': categories,
        'collections': collections,
        'colors': colors,
        'fabrics': fabrics,
        'occasions': occasions,
        'current_filters': request.GET,
    }
    return render(request, 'shop/catalog.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product.objects.prefetch_related('images', 'categories', 'reviews__user'), slug=slug, is_active=True)
    related_products = Product.objects.filter(is_active=True, categories__in=product.categories.all()).exclude(id=product.id).distinct()[:4]
    
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
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    
    # Check for coupon in session
    coupon_code = request.session.get('coupon_code')
    coupon = None
    discount = 0
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            if coupon.is_valid(subtotal):
                discount = coupon.calculate_discount(subtotal)
            else:
                del request.session['coupon_code']
                messages.warning(request, "Coupon became invalid.")
        except Coupon.DoesNotExist:
            del request.session['coupon_code']
            
    # Calculate tax & shipping
    tax_percent = settings_obj.tax_percentage
    tax = (subtotal - discount) * (tax_percent / Decimal('100'))
    
    shipping = settings_obj.shipping_charge
    if subtotal - discount >= settings_obj.free_shipping_limit:
        shipping = 0
        
    grand_total = subtotal - discount + tax + shipping

    context = {
        'cart': cart,
        'subtotal': subtotal,
        'coupon': coupon,
        'discount': discount,
        'tax': tax,
        'shipping': shipping,
        'grand_total': grand_total,
    }
    return render(request, 'shop/cart.html', context)

def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    quantity = int(request.POST.get('quantity', 1))
    
    if product.stock < quantity:
        messages.error(request, "Insufficient stock available.")
        return redirect(request.META.get('HTTP_REFERER', 'shop:catalog'))
        
    cart = _get_or_create_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.save()
    
    messages.success(request, f"Added {product.name} to your Cart.")
    return redirect('shop:cart_detail')

def cart_update(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    quantity = int(request.POST.get('quantity', 1))
    
    if cart_item.product.stock < quantity:
        messages.error(request, "Insufficient stock available.")
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
    if request.method == 'POST':
        code = request.POST.get('coupon_code')
        cart = _get_or_create_cart(request)
        subtotal = sum(item.get_total_price() for item in cart.items.all())
        
        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
            if coupon.is_valid(subtotal):
                request.session['coupon_code'] = coupon.code
                messages.success(request, f"Coupon '{code}' applied successfully!")
            else:
                messages.error(request, "Coupon is expired, fully used, or minimum purchase amount not met.")
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid coupon code.")
            
    return redirect('shop:cart_detail')

def remove_coupon(request):
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
        messages.success(request, "Coupon removed.")
    return redirect('shop:cart_detail')

@customer_required
def checkout(request):
        
    cart = _get_or_create_cart(request)
    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('shop:cart_detail')
        
    settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
    addresses = Address.objects.filter(user=request.user)
    
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    
    # Coupon calculation
    coupon_code = request.session.get('coupon_code')
    coupon = None
    discount = 0
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            if coupon.is_valid(subtotal):
                discount = coupon.calculate_discount(subtotal)
        except Coupon.DoesNotExist:
            pass
            
    tax_percent = settings_obj.tax_percentage
    tax = (subtotal - discount) * (tax_percent / Decimal('100'))
    
    shipping = settings_obj.shipping_charge
    if subtotal - discount >= settings_obj.free_shipping_limit:
        shipping = 0
        
    grand_total = subtotal - discount + tax + shipping

    context = {
        'cart': cart,
        'addresses': addresses,
        'subtotal': subtotal,
        'coupon': coupon,
        'discount': discount,
        'tax': tax,
        'shipping': shipping,
        'grand_total': grand_total,
    }
    return render(request, 'shop/checkout.html', context)

@customer_required
def order_create(request):
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
        payment_method = request.POST.get('payment_method', 'COD')
        
        # Calculate pricing
        settings_obj = WebsiteSetting.objects.first() or WebsiteSetting()
        subtotal = sum(item.get_total_price() for item in cart.items.all())
        
        # Coupon
        coupon_code = request.session.get('coupon_code')
        coupon = None
        discount = 0
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                if coupon.is_valid(subtotal):
                    discount = coupon.calculate_discount(subtotal)
            except Coupon.DoesNotExist:
                pass
                
        tax_percent = settings_obj.tax_percentage
        tax = (subtotal - discount) * (tax_percent / Decimal('100'))
        
        shipping = settings_obj.shipping_charge
        if subtotal - discount >= settings_obj.free_shipping_limit:
            shipping = 0
            
        grand_total = subtotal - discount + tax + shipping
        
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
            payment_method=payment_method,
            payment_status='PENDING' if payment_method == 'COD' else 'PAID', # stub paid for online placeholder
            order_status='PENDING',
            subtotal=subtotal,
            shipping_cost=shipping,
            tax_amount=tax,
            discount_amount=discount,
            grand_total=grand_total,
            coupon_used=coupon
        )
        
        # Move CartItems to OrderItems and decrement stock
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.offer_price
            )
            item.product.stock -= item.quantity
            item.product.save()
            
        # Update Coupon usage
        if coupon:
            coupon.used_count += 1
            coupon.save()
            del request.session['coupon_code']
            
        # Clear Cart
        cart.items.all().delete()
        
        messages.success(request, f"Order #{order_number} placed successfully!")
        return render(request, 'shop/order_success.html', {'order': order})
        
    return redirect('shop:checkout')

@customer_required
def order_detail(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), order_number=order_number, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})

@customer_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 5))
        comment = request.POST.get('comment')
        image = request.FILES.get('image')
        
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment,
            image=image
        )
        messages.success(request, "Your review has been submitted successfully and is pending administrator approval.")
        
    return redirect(request.META.get('HTTP_REFERER', 'shop:product_detail'))
