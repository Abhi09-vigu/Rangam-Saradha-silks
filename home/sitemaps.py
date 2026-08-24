from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from shop.models import Product, Category
from home.models import CMSPage

class StaticViewSitemap(Sitemap):
    priority = 0.9
    changefreq = 'daily'

    def items(self):
        return ['home:index', 'shop:catalog', 'home:contact', 'home:faq']

    def location(self, item):
        return reverse(item)

class CMSPageSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        try:
            from home.views import DEFAULT_CMS_PAGES
            for slug, data in DEFAULT_CMS_PAGES.items():
                CMSPage.objects.get_or_create(
                    slug=slug,
                    defaults={'title': data['title'], 'content': data['content']}
                )
        except Exception:
            pass
        return CMSPage.objects.all().order_by('id')

    def location(self, item):
        return reverse('home:cms_page', kwargs={'slug': item.slug})

class CategorySitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return Category.objects.filter(is_active=True)

    def location(self, item):
        return f"{reverse('shop:catalog')}?category={item.slug}"

class ProductSitemap(Sitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        return Product.objects.filter(is_active=True).order_by('-updated_at')

    def lastmod(self, item):
        return item.updated_at

    def location(self, item):
        return reverse('shop:product_detail', kwargs={'slug': item.slug})
