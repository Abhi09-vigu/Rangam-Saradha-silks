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

    def priority(self, item):
        priorities = {
            'home:index': 1.0,
            'shop:categories': 0.9,
            'shop:catalog': 0.9,
            'home:contact': 0.8,
            'home:faq': 0.8,
        }
        return priorities.get(item, 0.8)

    def changefreq(self, item):
        freqs = {
            'home:index': 'daily',
            'shop:categories': 'weekly',
            'shop:catalog': 'daily',
            'home:contact': 'monthly',
            'home:faq': 'monthly',
        }
        return freqs.get(item, 'weekly')


class CMSPageSitemap(BaseSitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return CMSPage.objects.all().order_by('id')

    def location(self, item):
        return reverse('home:cms_page', kwargs={'slug': item.slug})

    def priority(self, item):
        if item.slug == 'about-us':
            return 0.8
        return 0.5

    def changefreq(self, item):
        if item.slug == 'about-us':
            return 'monthly'
        return 'yearly'


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
        return Product.objects.filter(is_active=True, stock__gt=0).order_by('-updated_at')

    def lastmod(self, item):
        return item.updated_at

    def location(self, item):
        return reverse('shop:product_detail', kwargs={'slug': item.slug})

