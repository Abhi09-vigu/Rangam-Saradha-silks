import time
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date
from django.shortcuts import render, redirect
from .models import WebsiteSetting

class SeparateSessionMiddleware(SessionMiddleware):
    def process_request(self, request):
        cookie_name = 'admin_sessionid' if request.path.startswith('/admin/') else 'sessionid'
        request._session_cookie_name = cookie_name
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response
            
        cookie_name = getattr(request, '_session_cookie_name', 'sessionid')

        # Intercept redirection after admin login POST to prevent going to storefront
        if request.path.startswith('/admin/login/') and response.status_code == 302:
            redirect_to = response.get('Location')
            if redirect_to == '/' or redirect_to == settings.LOGIN_REDIRECT_URL:
                response['Location'] = '/admin/'

        if empty:
            response.set_cookie(
                cookie_name,
                '',
                max_age=0,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                secure=settings.SESSION_COOKIE_SECURE or None,
                httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            return response

        if modified or settings.SESSION_SAVE_EVERY_REQUEST:
            if request.session.get_expire_at_browser_close():
                max_age = None
                expires = None
            else:
                max_age = request.session.get_expiry_age()
                expires = http_date(time.time() + max_age)
                
            request.session.save()
            response.set_cookie(
                cookie_name,
                request.session.session_key,
                max_age=max_age,
                expires=expires,
                domain=settings.SESSION_COOKIE_DOMAIN,
                path=settings.SESSION_COOKIE_PATH,
                secure=settings.SESSION_COOKIE_SECURE or None,
                httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ('Cookie',))
        return response

class CustomMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Prevent customer users from accessing Django admin
        if request.path.startswith('/admin/'):
            if request.user.is_authenticated and not request.user.is_staff:
                from django.contrib.auth import logout
                logout(request)
                return redirect('accounts:login')
            return self.get_response(request)

        # Prompt customer users without phone number or usable password (e.g. Google sign-in) to complete profile
        if request.user.is_authenticated and not request.user.is_staff:
            exempt_prefixes = [
                '/accounts/complete-phone/',
                '/accounts/set-password/',
                '/accounts/logout/',
                '/static/',
                '/media/',
                '/admin/',
                '/api/',
            ]
            if not getattr(request.user, 'phone_number', None):
                if not any(request.path.startswith(prefix) for prefix in exempt_prefixes) and request.path not in ['/robots.txt', '/sitemap.xml', '/favicon.ico']:
                    from django.urls import reverse
                    redirect_target = reverse('accounts:complete_phone')
                    if request.path not in ['/', '/accounts/login/', '/accounts/register/']:
                        redirect_target += f"?next={request.path}"
                    return redirect(redirect_target)
            
        # Bypass maintenance check for static and media files, as well as robots.txt and sitemap XML
        if (
            request.path.startswith('/static/')
            or request.path.startswith('/media/')
            or request.path in ['/robots.txt', '/sitemap.xml']
            or request.path.startswith('/sitemap')
        ):
            return self.get_response(request)

        # Bypass maintenance check for logged-in staff users (inspecting admin session cookie)
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
                        return self.get_response(request)
            except Exception:
                pass

        # Check if maintenance mode is enabled in WebsiteSettings
        try:
            setting = WebsiteSetting.objects.first()
        except Exception:
            setting = None
        if setting and setting.maintenance_mode:
            return render(request, 'home/maintenance.html', status=503)

        response = self.get_response(request)

        # Sync lightweight auth state cookie for client-side bfcache / back-forward detection
        is_auth = '1' if (hasattr(request, 'user') and request.user.is_authenticated) else '0'
        if request.COOKIES.get('rss_auth_state') != is_auth:
            response.set_cookie(
                'rss_auth_state',
                is_auth,
                path='/',
                samesite='Lax',
                secure=settings.SESSION_COOKIE_SECURE or None,
            )

        # Prevent browser back/forward cache (bfcache) from serving stale dynamic HTML (e.g. stale login / cart)
        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type and not response.has_header('Cache-Control'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response

