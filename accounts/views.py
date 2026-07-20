from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .decorators import customer_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse
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

logger = logging.getLogger(__name__)

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
    return render(request, 'accounts/register.html', {'form': form})

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
        'active_tab': request.POST.get('login_type', 'phone')
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

    
    # Lazy import of Order to avoid circular imports
    from shop.models import Order
    orders = Order.objects.filter(user=user).order_by('-created_at')
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'orders': orders,
        'addresses': user.addresses.all(),
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
        
    messages.success(request, msg)
    return redirect(request.META.get('HTTP_REFERER', 'shop:product_detail'))

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
