from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
import random
from datetime import timedelta

from .models import CustomUser, Address, Wishlist
from .forms import (
    CustomUserCreationForm, UserProfileForm, AddressForm, 
    OTPVerificationForm, ForgotPasswordForm, ResetPasswordForm
)

def register_view(request):
    if request.user.is_authenticated and not request.user.is_staff:
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
    username = request.session.get('registration_username')
    if not username:
        messages.error(request, "Invalid registration session.")
        return redirect('accounts:register')
    
    user = get_object_or_404(CustomUser, username=username)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('otp_code')
            if user.otp_code == code and user.otp_expiry > timezone.now():
                user.is_verified = True
                user.is_active = True
                user.otp_code = None
                user.otp_expiry = None
                user.save()
                
                login(request, user)
                del request.session['registration_username']
                messages.success(request, "Account verified and logged in successfully!")
                return redirect('home:index')
            else:
                messages.error(request, "Invalid or expired OTP.")
    else:
        form = OTPVerificationForm()
    return render(request, 'accounts/verify_otp.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home:index')
    
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        
        # Try to authenticate by username
        user = authenticate(request, username=username_or_email, password=password)
        
        # Or try to authenticate by email
        if not user:
            try:
                user_obj = CustomUser.objects.get(email=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except CustomUser.DoesNotExist:
                pass
                
        if user:
            if user.is_active:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                next_url = request.GET.get('next', 'home:index')
                return redirect(next_url)
            else:
                messages.error(request, "Account is disabled. Please verify your OTP.")
                # Resend OTP flow placeholder
                return redirect('accounts:register')
        else:
            messages.error(request, "Invalid credentials.")
            
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('home:index')

@login_required
def profile_view(request):
    user = request.user
    if user.is_staff:
        messages.warning(request, "Please log in with a customer account to view profile.")
        return redirect('/accounts/login/?next=/accounts/profile/')
        
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
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

@login_required
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

@login_required
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

@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address deleted successfully.")
    return redirect('accounts:profile')

@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'accounts/wishlist.html', {'wishlist_items': items})

@login_required
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

@login_required
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
