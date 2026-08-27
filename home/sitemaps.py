from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from shop.models import Product, Category
from home.models import CMSPage


class BaseSitemap(Sitemap):
    """
    Base Sitemap class enforcing https protocol and canonical production domain.
    """
    protocol = 'https'

    def get_domain(self, site=None):
        return 'rangamsaradhasilks.com'


class StaticViewSitemap(BaseSitemap):
    priority = 0.9
    changefreq = 'daily'

    def items(self):
        return ['home:index', 'shop:categories', 'shop:catalog', 'home:contact', 'home:faq']

    def location(self, item):
        return reverse(item)


class CMSPageSitemap(BaseSitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return CMSPage.objects.all().order_by('id')

    def location(self, item):
        return reverse('home:cms_page', kwargs={'slug': item.slug})


class CategorySitemap(BaseSitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return Category.objects.filter(is_active=True).order_by('display_order', 'id')

    def location(self, item):
        return reverse('shop:category_detail', kwargs={'category_slug': item.slug})


class ProductSitemap(BaseSitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        return Product.objects.filter(is_active=True).order_by('-updated_at')

    def lastmod(self, item):
        return item.updated_at

    def location(self, item):
        return reverse('shop:product_detail', kwargs={'slug': item.slug})

