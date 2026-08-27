from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .decorators import customer_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST
import random
from datetime import timedelta
import logging

from .models import CustomUser, Address, Wishlist
from .forms import (
    CustomUserCreationForm, UserProfileForm, AddressForm, 
    OTPVerificationForm, ForgotPasswordForm, ResetPasswordForm,
    PhoneLoginForm
)

# Twilio Verify Client Helpers & Setup
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from django.core.mail import send_mail

logger = logging.getLogger(__name__)

def send_registration_welcome_email(user):
    """
    Sends an automatic welcome email to newly registered users via Google / Firebase OAuth.
    """
    if not user or not user.email:
        logger.warning("Skipping registration welcome email: User or user email address missing.")
        return False

    first_name = user.first_name or user.username or "Customer"
    subject = "Welcome to Rangam Saradha Silks!"

    body = (
        f"Dear {first_name},\n\n"
        f"Thank you for registering with Rangam Saradha Silks.\n\n"
        f"We are delighted to have you with us. Explore our collection of traditional silk sarees and discover something special for every occasion.\n\n"
        f"Visit our website:\n"
        f"https://rangamsaradhasilks.com/\n\n"
        f"Thank you for choosing Rangam Saradha Silks.\n\n"
        f"Warm regards,\n"
        f"Rangam Saradha Silks\n"
        f"https://rangamsaradhasilks.com/"
    )

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'Rangam Saradha Silks <rangamsaradhasilks@gmail.com>'

    try:
        sent_count = send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=True,
        )
        if sent_count == 0:
            logger.error(f"Failed to send welcome email to {user.email} (send_mail returned 0).")
        else:
            logger.info(f"Welcome email successfully sent to {user.email}.")
        return sent_count > 0
    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {str(e)}", exc_info=True)
        return False

def get_twilio_client():
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    if not account_sid or not auth_token:
        return None
    try:
        return Client(account_sid, auth_token)
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")
        return None

def is_twilio_configured():
    client = get_twilio_client()
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None)
    return client is not None and bool(service_sid)

def is_mock_mode():
    return settings.DEBUG and not is_twilio_configured()

def send_verification_otp(phone_number):
    client = get_twilio_client()
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None)
    if not client or not service_sid:
        return False, "Twilio configuration variables are missing or incorrect."
    try:
        verification = client.verify.v2.services(service_sid) \
                                       .verifications \
                                       .create(to=phone_number, channel='sms')
        return True, verification.status
    except TwilioRestException as e:
        logger.error(f"Twilio Verify send error for {phone_number}: {e.msg} (Code: {e.code})")
        return False, e.msg
    except Exception as e:
        logger.error(f"Error sending verification to {phone_number}: {str(e)}")
        return False, "Failed to send verification code. Please try again."

def check_verification_otp(phone_number, code):
    client = get_twilio_client()
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None)
    if not client or not service_sid:
        return False, "Twilio configuration variables are missing or incorrect."
    try:
        # Check code but NEVER print or log the code parameter for security
        verification_check = client.verify.v2.services(service_sid) \
                                             .verification_checks \
                                             .create(to=phone_number, code=code)
        if verification_check.status == 'approved':
            return True, "Verification successful."
        else:
            return False, "Invalid verification code."
    except TwilioRestException as e:
        logger.error(f"Twilio Verify check error for {phone_number}: {e.msg} (Code: {e.code})")
        return False, e.msg
    except Exception as e:
        logger.error(f"Error checking verification for {phone_number}: {str(e)}")
        return False, "Failed to verify code. Please try again."

def check_rate_limit(request):
    """
    Session-based rate limiting to prevent spamming Twilio requests.
    Enforces a 30-second cooldown and a maximum of 5 requests per 10 minutes.
    """
    now = timezone.now()
    
    # 30-second cooldown
    last_sent_str = request.session.get('last_otp_sent_time')
    if last_sent_str:
        try:
            last_sent = timezone.datetime.fromisoformat(last_sent_str)
            time_diff = (now - last_sent).total_seconds()
            if time_diff < 30:
                return False, f"Please wait {int(30 - time_diff)} seconds before requesting another code."
        except ValueError:
            pass

    # Max 5 requests per 10 minutes
    otp_requests = request.session.get('otp_requests_history', [])
    ten_minutes_ago = now - timedelta(minutes=10)
    
    # Filter out requests older than 10 minutes
    valid_requests = []
    for req in otp_requests:
        try:
            if timezone.datetime.fromisoformat(req) > ten_minutes_ago:
                valid_requests.append(req)
        except ValueError:
            pass
    otp_requests = valid_requests
    
    if len(otp_requests) >= 5:
        return False, "Too many verification requests. Please try again in 10 minutes."
        
    # Record this request
    otp_requests.append(now.isoformat())
    request.session['otp_requests_history'] = otp_requests
    request.session['last_otp_sent_time'] = now.isoformat()
    return True, None

def merge_carts_after_login(request, user, old_session_key):
    """
    Transfers any session-based cart items to the authenticated user's cart on login.
    """
    from shop.models import Cart, CartItem
    if not old_session_key:
        return
        
    guest_cart = Cart.objects.filter(session_key=old_session_key).first()
    if guest_cart and guest_cart.items.exists():
        user_cart, created = Cart.objects.get_or_create(user=user)
        
        for guest_item in guest_cart.items.all():
            user_item = CartItem.objects.filter(cart=user_cart, product=guest_item.product).first()
            if user_item:
                user_item.quantity += guest_item.quantity
                user_item.save()
                guest_item.delete()
            else:
                guest_item.cart = user_cart
                guest_item.save()
                
        # Delete guest cart after merge
        guest_cart.delete()

def register_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            logout(request)
        else:
            return redirect('home:index')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False # Deactivate until OTP verified
            # Generate mock OTP
            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expiry = timezone.now() + timedelta(minutes=10)
            user.save()
            
            # Save username in session for verification
            request.session['registration_username'] = user.username
            
            # Output message with mock OTP for easy developer access (instead of sending SMS/Email)
            messages.success(request, f"Registration success! Use mock verification code: {otp}")
            return redirect('accounts:verify_otp')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {
        'form': form,
        'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        'firebase_config': getattr(settings, 'FIREBASE_CONFIG', {})
    })

def verify_otp(request):
    phone_number = request.session.get('otp_phone_number')
    username = request.session.get('registration_username')
    
    if not phone_number and not username:
        messages.error(request, "Invalid verification session. Please log in or register.")
        return redirect('accounts:login')
        
    is_phone_login = bool(phone_number)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('otp_code')
            
            if is_phone_login:
                attempts = request.session.get('otp_verify_attempts', 0)
                if attempts >= 5:
                    request.session.pop('otp_phone_number', None)
                    request.session.pop('otp_verify_attempts', None)
                    messages.error(request, "Too many failed attempts. Please request a new verification code.")
                    return redirect('accounts:login')
                
                if is_mock_mode():
                    success = (code == '123456')
                    err_msg = "Invalid mock code. Use '123456'."
                else:
                    success, err_msg = check_verification_otp(phone_number, code)
                    
                if success:
                    user = CustomUser.objects.filter(phone_number=phone_number).first()
                    if not user:
                        # Create customer account
                        username_base = f"user_{phone_number.replace('+', '')}"
                        username_candidate = username_base
                        import uuid
                        while CustomUser.objects.filter(username=username_candidate).exists():
                            username_candidate = f"{username_base}_{uuid.uuid4().hex[:6]}"
                            
                        user = CustomUser.objects.create_user(
                            username=username_candidate,
                            phone_number=phone_number,
                            is_verified=True,
                            is_active=True
                        )
                        user.set_unusable_password()
                        user.save()
                        messages.success(request, "Account created successfully using your phone number.")
                    
                    old_session_key = request.session.session_key
                    login(request, user)
                    merge_carts_after_login(request, user, old_session_key)
                    
                    request.session.pop('otp_phone_number', None)
                    request.session.pop('otp_verify_attempts', None)
                    
                    messages.success(request, f"Welcome back, {user.username}!")
                    
                    next_url = request.GET.get('next')
                    if not next_url or next_url.startswith('/admin'):
                        next_url = 'home:index'
                    return redirect(next_url)
                else:
                    attempts += 1
                    request.session['otp_verify_attempts'] = attempts
                    messages.error(request, f"Invalid code: {err_msg} (Attempt {attempts}/5)")
            else:
                user = get_object_or_404(CustomUser, username=username)
                if user.otp_code == code and user.otp_expiry > timezone.now():
                    user.is_verified = True
                    user.is_active = True
                    user.otp_code = None
                    user.otp_expiry = None
                    user.save()
                    
                    old_session_key = request.session.session_key
                    login(request, user)
                    merge_carts_after_login(request, user, old_session_key)
                    
                    del request.session['registration_username']
                    messages.success(request, "Account verified and logged in successfully!")
                    return redirect('home:index')
                else:
                    messages.error(request, "Invalid or expired OTP.")
    else:
        form = OTPVerificationForm()
        
    return render(request, 'accounts/verify_otp.html', {
        'form': form,
        'phone_number': phone_number,
        'username': username,
        'is_phone_login': is_phone_login
    })

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            logout(request)
        else:
            return redirect('home:index')
            
    phone_form = PhoneLoginForm()
    
    if request.method == 'POST':
        login_type = request.POST.get('login_type')
        
        if login_type == 'phone':
            phone_form = PhoneLoginForm(request.POST)
            if phone_form.is_valid():
                phone_number = phone_form.cleaned_data.get('phone_number')
                
                allowed, err_msg = check_rate_limit(request)
                if not allowed:
                    messages.error(request, err_msg)
                    return render(request, 'accounts/login.html', {
                        'phone_form': phone_form,
                        'active_tab': 'phone'
                    })
                
                if is_mock_mode():
                    success = True
                    msg = "Development Mock Mode: Code sent successfully. Use code 123456 to log in."
                    logger.info(f"MOCK OTP sent to {phone_number}. Code: 123456")
                else:
                    success, msg = send_verification_otp(phone_number)
                
                if success:
                    request.session['otp_phone_number'] = phone_number
                    request.session['otp_verify_attempts'] = 0
                    messages.success(request, f"Verification code sent to {phone_number}. " + (msg if is_mock_mode() else ""))
                    return redirect('accounts:verify_otp')
                else:
                    messages.error(request, f"Error sending verification code: {msg}")
            else:
                messages.error(request, "Please enter a valid mobile number.")
                return render(request, 'accounts/login.html', {
                    'phone_form': phone_form,
                    'active_tab': 'phone'
                })
        else:
            username_or_email = request.POST.get('username')
            password = request.POST.get('password')
            
            user = authenticate(request, username=username_or_email, password=password)
            if not user:
                try:
                    user_obj = CustomUser.objects.get(email=username_or_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except CustomUser.DoesNotExist:
                    pass
                    
            if user:
                if user.is_staff or user.is_superuser:
                    messages.error(request, "Admin accounts must login through the Admin Panel.")
                    return redirect('accounts:login')
                    
                if user.is_active:
                    old_session_key = request.session.session_key
                    login(request, user)
                    merge_carts_after_login(request, user, old_session_key)
                    
                    messages.success(request, f"Welcome back, {user.username}!")
                    next_url = request.GET.get('next')
                    if not next_url or next_url.startswith('/admin'):
                        next_url = 'home:index'
                    return redirect(next_url)
                else:
                    messages.error(request, "Account is disabled. Please verify your OTP.")
                    return redirect('accounts:register')
            else:
                messages.error(request, "Invalid credentials.")
                
    return render(request, 'accounts/login.html', {
        'phone_form': phone_form,
        'active_tab': request.POST.get('login_type', 'password'),
        'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        'firebase_config': getattr(settings, 'FIREBASE_CONFIG', {})
    })

def resend_otp_view(request):
    phone_number = request.session.get('otp_phone_number')
    if not phone_number:
        messages.error(request, "No active verification session. Please try logging in again.")
        return redirect('accounts:login')
        
    allowed, err_msg = check_rate_limit(request)
    if not allowed:
        messages.error(request, err_msg)
        return redirect('accounts:verify_otp')
        
    if is_mock_mode():
        success = True
        msg = "Development Mock Mode: Code sent successfully. Use code 123456 to log in."
        logger.info(f"MOCK OTP resent to {phone_number}. Code: 123456")
    else:
        success, msg = send_verification_otp(phone_number)
        
    if success:
        request.session['otp_verify_attempts'] = 0
        messages.success(request, f"Verification code resent to {phone_number}. " + (msg if is_mock_mode() else ""))
    else:
        messages.error(request, f"Error resending verification code: {msg}")
        
    return redirect('accounts:verify_otp')


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('home:index')

@customer_required
def profile_view(request):
    user = request.user
        
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=user)

    
    # Lazy import of Order and CallBooking to avoid circular imports
    from shop.models import Order, CallBooking
    orders = Order.objects.filter(user=user).order_by('-created_at')
    
    # Retrieve all call bookings belonging to the currently logged-in user
    call_bookings = CallBooking.objects.filter(
        Q(user=user) | (Q(email__iexact=user.email) & Q(user__isnull=True))
    ).select_related('product').prefetch_related('product__images').order_by('-created_at')
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'orders': orders,
        'call_bookings': call_bookings,
        'addresses': user.addresses.all(),
    })

@customer_required
def call_booking_detail(request, booking_ref):
    """
    View complete details of a specific call booking.
    Enforces security: only the authenticated customer who owns the booking
    (request.user or booking user matching request.user/verified email) can access it.
    Returns 404 when the booking does not belong to the logged-in customer.
    """
    from shop.models import CallBooking
    user = request.user
    
    booking = CallBooking.objects.select_related('product').prefetch_related('product__images').filter(
        Q(booking_reference=booking_ref) & (Q(user=user) | (Q(email__iexact=user.email) & Q(user__isnull=True)))
    ).first()
    
    if not booking:
        raise Http404("Booking not found or access denied.")
        
    return render(request, 'accounts/call_booking_detail.html', {
        'booking': booking,
    })

@customer_required
def address_create(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "Address added successfully.")
            return redirect('accounts:profile')
    else:
        form = AddressForm()
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Add Address'})

@customer_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully.")
            return redirect('accounts:profile')
    else:
        form = AddressForm(instance=address)
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Edit Address'})

@customer_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address deleted successfully.")
    return redirect('accounts:profile')

@customer_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'accounts/wishlist.html', {'wishlist_items': items})

@customer_required
def toggle_wishlist(request, product_id):
    # Lazy import
    from shop.models import Product
    product = get_object_or_404(Product, id=product_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product)
    
    if wishlist_item.exists():
        wishlist_item.delete()
        added = False
        msg = "Product removed from your Wishlist."
    else:
        Wishlist.objects.create(user=request.user, product=product)
        added = True
        msg = "Product added to your Wishlist."
        
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'message': msg})
        
    from django.urls import reverse
    messages.success(request, msg)
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer if referer else reverse('shop:product_detail', args=[product.slug]))

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email_or_phone = form.cleaned_data.get('email_or_phone')
            # Look up user by email or phone
            try:
                if '@' in email_or_phone:
                    user = CustomUser.objects.get(email=email_or_phone)
                else:
                    user = CustomUser.objects.get(phone_number=email_or_phone)
                
                # Generate mock OTP code
                otp = str(random.randint(100000, 999999))
                user.otp_code = otp
                user.otp_expiry = timezone.now() + timedelta(minutes=10)
                user.save()
                
                request.session['reset_password_username'] = user.username
                messages.success(request, f"Verification code sent! Use mock code: {otp}")
                return redirect('accounts:verify_reset_otp')
            except CustomUser.DoesNotExist:
                messages.error(request, "No user found with that email or phone number.")
    else:
        form = ForgotPasswordForm()
    return render(request, 'accounts/forgot_password.html', {'form': form})

def verify_reset_otp(request):
    username = request.session.get('reset_password_username')
    if not username:
        messages.error(request, "Invalid reset password session.")
        return redirect('accounts:forgot_password')
        
    user = get_object_or_404(CustomUser, username=username)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('otp_code')
            if user.otp_code == code and user.otp_expiry > timezone.now():
                # Correct code, proceed to reset password page
                request.session['reset_password_allowed'] = True
                user.otp_code = None
                user.otp_expiry = None
                user.save()
                return redirect('accounts:reset_password')
            else:
                messages.error(request, "Invalid or expired verification code.")
    else:
        form = OTPVerificationForm()
    return render(request, 'accounts/verify_reset_otp.html', {'form': form})

def reset_password(request):
    if not request.session.get('reset_password_allowed') or not request.session.get('reset_password_username'):
        messages.error(request, "Unauthorized password reset attempt.")
        return redirect('accounts:forgot_password')
        
    username = request.session.get('reset_password_username')
    user = get_object_or_404(CustomUser, username=username)
    
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data.get('new_password')
            user.set_password(new_password)
            user.save()
            
            # Clean up sessions
            del request.session['reset_password_username']
            del request.session['reset_password_allowed']
            
            messages.success(request, "Password reset successfully! Please login with your new password.")
            return redirect('accounts:login')
    else:
        form = ResetPasswordForm()
    return render(request, 'accounts/reset_password.html', {'form': form})

@customer_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) # keep user logged in
            messages.success(request, "Password updated successfully.")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})

from django.views.decorators.csrf import csrf_exempt
import json
import requests

@csrf_exempt
@require_POST
def google_login_view(request):
    """
    Handles Google Authentication (Sign-In / Sign-Up).
    Accepts Google ID Token (credential) or access_token via AJAX POST.
    Validates token against Google's OAuth2 API endpoints.
    Finds or creates CustomUser and authenticates session.
    """
    try:
        # Parse payload from JSON body or POST form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except Exception:
                data = request.POST
        else:
            data = request.POST

        id_token_str = data.get('id_token') or data.get('credential') or data.get('token')
        access_token = data.get('access_token')

        if not id_token_str and not access_token:
            return JsonResponse({'status': 'error', 'message': 'Google credential token missing.'}, status=400)

        google_user_data = None

        # Verify Google ID Token via Google's official tokeninfo endpoint
        if id_token_str:
            resp = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}", timeout=8)
            if resp.status_code == 200:
                payload = resp.json()
                google_user_data = {
                    'email': payload.get('email'),
                    'email_verified': str(payload.get('email_verified', '')).lower() in ['true', '1'],
                    'google_id': payload.get('sub'),
                    'name': payload.get('name', ''),
                    'given_name': payload.get('given_name', ''),
                    'family_name': payload.get('family_name', ''),
                    'picture': payload.get('picture', ''),
                }
            else:
                logger.warning(f"Google Token Verification failed: {resp.text}")

        # Fallback verification via Google UserInfo API if access_token was passed
        if not google_user_data and access_token:
            resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=8)
            if resp.status_code == 200:
                payload = resp.json()
                google_user_data = {
                    'email': payload.get('email'),
                    'email_verified': str(payload.get('email_verified', '')).lower() in ['true', '1'],
                    'google_id': payload.get('sub'),
                    'name': payload.get('name', ''),
                    'given_name': payload.get('given_name', ''),
                    'family_name': payload.get('family_name', ''),
                    'picture': payload.get('picture', ''),
                }

        if not google_user_data or not google_user_data.get('email'):
            return JsonResponse({'status': 'error', 'message': 'Google authentication failed. Invalid token.'}, status=400)

        email = google_user_data['email'].strip().lower()
        google_id = google_user_data['google_id']
        picture_url = google_user_data.get('picture', '')
        first_name = google_user_data.get('given_name') or google_user_data.get('name') or ''
        last_name = google_user_data.get('family_name') or ''

        # Search for existing user by google_id or email
        user = CustomUser.objects.filter(google_id=google_id).first()
        if not user:
            user = CustomUser.objects.filter(email__iexact=email).first()

        old_session_key = request.session.session_key

        if user:
            # Update user attributes
            if not user.google_id:
                user.google_id = google_id
            user.auth_provider = 'google'
            if picture_url and not user.profile_picture_url:
                user.profile_picture_url = picture_url
            if first_name and not user.first_name:
                user.first_name = first_name
            if last_name and not user.last_name:
                user.last_name = last_name
            user.is_verified = True
            user.is_active = True
            user.save()
        else:
            # Create new user
            username_base = email.split('@')[0]
            username_candidate = username_base
            import uuid
            while CustomUser.objects.filter(username=username_candidate).exists():
                username_candidate = f"{username_base}_{uuid.uuid4().hex[:4]}"

            user = CustomUser.objects.create_user(
                username=username_candidate,
                email=email,
                first_name=first_name,
                last_name=last_name,
                auth_provider='google',
                google_id=google_id,
                profile_picture_url=picture_url,
                is_verified=True,
                is_active=True
            )
            user.set_unusable_password()
            user.save()
            send_registration_welcome_email(user)

        # Log in user persistently
        login(request, user)

        # Merge guest cart if helper is defined in module
        try:
            from shop.views import merge_carts_after_login
            merge_carts_after_login(request, user, old_session_key)
        except Exception as e:
            logger.info(f"Cart merge check: {e}")

        # Redirect destination
        next_url = data.get('next') or request.GET.get('next')
        if not next_url or next_url.startswith('/admin'):
            next_url = '/'

        messages.success(request, f"Welcome back, {user.first_name or user.username}! Authenticated via Google.")

        return JsonResponse({
            'status': 'success',
            'message': 'Google authentication successful.',
            'redirect_url': next_url,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.get_full_name() or user.username,
                'avatar': user.get_avatar_url()
            }
        })

    except Exception as e:
        logger.error(f"Google login exception: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Server authentication error: {str(e)}'}, status=500)


from firebase_admin import auth as firebase_auth

@csrf_exempt
@require_POST
def firebase_login_view(request):
    """
    Handles Firebase Google Authentication.
    Accepts Firebase ID Token from frontend, verifies it using Firebase Admin SDK auth.verify_id_token().
    Finds or creates CustomUser in PostgreSQL database and logs user in.
    Stores users ONLY in PostgreSQL (no Firestore / Firebase DB).
    """
    try:
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except Exception:
                data = request.POST
        else:
            data = request.POST

        id_token = data.get('id_token') or data.get('token') or data.get('credential')
        if not id_token:
            return JsonResponse({'status': 'error', 'message': 'Firebase ID token is missing.'}, status=400)

        # Verify Firebase ID Token using Firebase Admin SDK
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
        except Exception as ve:
            logger.error(f"Firebase token verification error: {str(ve)}")
            return JsonResponse({'status': 'error', 'message': f'Invalid Firebase token: {str(ve)}'}, status=400)

        uid = decoded_token.get('uid')
        email = decoded_token.get('email', '').strip().lower()
        name = decoded_token.get('name', '')
        picture_url = decoded_token.get('picture', '')

        if not email or not uid:
            return JsonResponse({'status': 'error', 'message': 'Email address not provided by Firebase token.'}, status=400)

        # Parse name components
        name_parts = name.split() if name else []
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''

        # Look up existing user in PostgreSQL
        user = CustomUser.objects.filter(firebase_uid=uid).first()
        if not user:
            user = CustomUser.objects.filter(email__iexact=email).first()

        old_session_key = request.session.session_key

        if user:
            # Update user fields
            if not user.firebase_uid:
                user.firebase_uid = uid
            user.auth_provider = 'google'
            if picture_url and not user.profile_picture_url:
                user.profile_picture_url = picture_url
            if first_name and not user.first_name:
                user.first_name = first_name
            if last_name and not user.last_name:
                user.last_name = last_name
            user.is_verified = True
            user.is_active = True
            user.save()
        else:
            # Create new user in PostgreSQL
            username_base = email.split('@')[0]
            username_candidate = username_base
            import uuid
            while CustomUser.objects.filter(username=username_candidate).exists():
                username_candidate = f"{username_base}_{uuid.uuid4().hex[:4]}"

            user = CustomUser.objects.create_user(
                username=username_candidate,
                email=email,
                first_name=first_name,
                last_name=last_name,
                auth_provider='google',
                firebase_uid=uid,
                profile_picture_url=picture_url,
                is_verified=True,
                is_active=True
            )
            user.set_unusable_password()
            user.save()
            send_registration_welcome_email(user)

        # Establish persistent Django session login
        login(request, user)

        # Merge guest cart items
        try:
            from shop.views import merge_carts_after_login
            merge_carts_after_login(request, user, old_session_key)
        except Exception as e:
            logger.info(f"Cart merge error check: {e}")

        next_url = data.get('next') or request.GET.get('next')
        if not next_url or next_url.startswith('/admin'):
            next_url = '/'

        messages.success(request, f"Welcome, {user.first_name or user.username}! Authenticated via Firebase Google Sign-In.")

        return JsonResponse({
            'status': 'success',
            'message': 'Firebase Google Authentication successful.',
            'redirect_url': next_url,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.get_full_name() or user.username,
                'avatar': user.get_avatar_url()
            }
        })

    except Exception as e:
        logger.error(f"Firebase login view error: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Authentication failure: {str(e)}'}, status=500)
