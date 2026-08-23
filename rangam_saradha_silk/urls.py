"""
URL configuration for rangam_saradha_silk project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.contrib.sitemaps.views import sitemap
from rangam_saradha_silk.admin import custom_admin_site
from home.views import ContactFormAPIView, robots_txt
from home.sitemaps import StaticViewSitemap, CMSPageSitemap, CategorySitemap, ProductSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'cms': CMSPageSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
}

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/logo.jpg', permanent=True)),
    path('admin/', custom_admin_site.urls),
    path('accounts/', include('accounts.urls')),
    path('shop/', include('shop.urls')),
    path('api/contact/', ContactFormAPIView.as_view(), name='api_contact'),
    path('', include('home.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

