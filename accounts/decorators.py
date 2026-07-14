from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def customer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.is_staff or request.user.is_superuser:
            messages.error(request, "Admin accounts must login through the Admin Panel.")
            from django.contrib.auth import logout
            logout(request)
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "You do not have permission to access the Admin Panel.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
