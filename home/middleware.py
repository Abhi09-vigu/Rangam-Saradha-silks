from django.shortcuts import render
from .models import WebsiteSetting

class CustomMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Bypass maintenance check for admin pages
        if request.path.startswith('/admin/'):
            return self.get_response(request)
            
        # Bypass maintenance check for logged-in staff users on the frontend
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)

        # Check if maintenance mode is enabled in WebsiteSettings
        try:
            setting = WebsiteSetting.objects.first()
        except Exception:
            setting = None
        if setting and setting.maintenance_mode:
            return render(request, 'home/maintenance.html', status=503)

        return self.get_response(request)
