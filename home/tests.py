from django.test import TestCase
import xml.etree.ElementTree as ET
from django.test import TestCase, override_settings
from django.urls import reverse
from shop.models import Category, Product
from home.models import CMSPage, FAQ, WebsiteSetting, ContactInfo

# Create your tests here.

@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class RobotsTxtTest(TestCase):
    """
    Tests for robots.txt configuration ensuring search engines are directed
    correctly and private / transactional routes are disallowed.
    """

    def test_robots_txt_status_and_content_type(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_robots_txt_rules(self):
        response = self.client.get('/robots.txt')
        content = response.content.decode('utf-8')

        self.assertIn('User-agent: *', content)
        self.assertIn('Disallow: /admin/', content)
        self.assertIn('Disallow: /accounts/', content)
        self.assertIn('Disallow: /shop/cart/', content)
        self.assertIn('Disallow: /shop/checkout/', content)
        self.assertIn('Disallow: /shop/order/', content)
        self.assertIn('Disallow: /shop/booking/', content)
        self.assertIn('Disallow: /shop/coupon/', content)
        self.assertIn('Disallow: /api/', content)
        self.assertIn('Disallow: /debug-db/', content)
        self.assertIn('Allow: /', content)
        self.assertIn('Sitemap: https://rangamsaradhasilks.com/sitemap.xml', content)

    def test_robots_txt_no_unwanted_domains_or_queries(self):
        response = self.client.get('/robots.txt')
        content = response.content.decode('utf-8')

        self.assertNotIn('localhost', content)
        self.assertNotIn('127.0.0.1', content)
        self.assertNotIn('?', content)


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class SitemapXmlTest(TestCase):
    """
    Tests for sitemap.xml ensuring:
    1. Valid XML structure
    2. Canonical domain https://rangamsaradhasilks.com/
    3. Proper inclusion of active items only (CMS, Categories, Products, Static views)
    4. Every sitemap URL returns HTTP 200
    5. Zero query-strings, localhost, or 127.0.0.1 references
    """

    def setUp(self):
        WebsiteSetting.objects.create(website_name="Rangam Saradha Silks")
        ContactInfo.objects.create(
            phone="+91 98765 43210",
            email="contact@rangamsaradhasilks.com",
            address="Kanchipuram, Tamil Nadu",
        )

        # Create CMS pages
        self.cms_about = CMSPage.objects.create(
            title="About Us",
            slug="about-us",
            content="About our heritage sarees."
        )
        self.cms_privacy = CMSPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="Privacy policy content."
        )

        # Create active and inactive categories
        self.active_category = Category.objects.create(
            name="Kanchipuram Silk",
            slug="kanchipuram-silk",
            is_active=True,
            display_order=1,
        )
        self.inactive_category = Category.objects.create(
            name="Draft Category",
            slug="draft-category",
            is_active=False,
            display_order=99,
        )

        # Create active and inactive products
        self.active_product = Product.objects.create(
            name="Royal Red Pure Kanchipuram Silk Saree",
            slug="royal-red-pure-kanchipuram-silk-saree",
            sku="RSS-001",
            price=12500.00,
            stock=5,
            is_active=True,
        )
        self.active_product.categories.add(self.active_category)

        self.inactive_product = Product.objects.create(
            name="Unpublished Saree",
            slug="unpublished-saree",
            sku="RSS-999",
            price=9999.00,
            stock=0,
            is_active=False,
        )

    def test_sitemap_xml_status_and_headers(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('xml', response['Content-Type'])

    def test_sitemap_xml_validity_and_domain(self):
        response = self.client.get('/sitemap.xml')
        content = response.content.decode('utf-8')

        # No localhost or 127.0.0.1
        self.assertNotIn('localhost', content)
        self.assertNotIn('127.0.0.1', content)

        # Parse XML
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [elem.text for elem in root.findall('ns:url/ns:loc', namespace)]

        # Must have URLs
        self.assertGreater(len(urls), 0)

        # All URLs must start with https://rangamsaradhasilks.com/ and have no query strings
        for url in urls:
            self.assertTrue(
                url.startswith('https://rangamsaradhasilks.com/'),
                f"URL does not use canonical https domain: {url}"
            )
            self.assertNotIn('?', url, f"URL in sitemap contains query string: {url}")

    def test_sitemap_contains_expected_pages(self):
        response = self.client.get('/sitemap.xml')
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = {elem.text for elem in root.findall('ns:url/ns:loc', namespace)}

        # Core static pages
        self.assertIn('https://rangamsaradhasilks.com/', urls)
        self.assertIn('https://rangamsaradhasilks.com/shop/categories/', urls)
        self.assertIn('https://rangamsaradhasilks.com/shop/', urls)
        self.assertIn('https://rangamsaradhasilks.com/contact/', urls)
        self.assertIn('https://rangamsaradhasilks.com/faqs/', urls)

        # CMS pages
        self.assertIn('https://rangamsaradhasilks.com/page/about-us/', urls)
        self.assertIn('https://rangamsaradhasilks.com/page/privacy-policy/', urls)

        # Active category and active product
        self.assertIn('https://rangamsaradhasilks.com/shop/category/kanchipuram-silk/', urls)
        self.assertIn('https://rangamsaradhasilks.com/shop/product/royal-red-pure-kanchipuram-silk-saree/', urls)

        # Inactive category and inactive product must NOT be present
        self.assertNotIn('https://rangamsaradhasilks.com/shop/category/draft-category/', urls)
        self.assertNotIn('https://rangamsaradhasilks.com/shop/product/unpublished-saree/', urls)

    def test_every_sitemap_url_returns_200(self):
        """
        Extract every URL from sitemap.xml and verify that it resolves to HTTP 200.
        """
        response = self.client.get('/sitemap.xml')
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [elem.text for elem in root.findall('ns:url/ns:loc', namespace)]

        domain_prefix = 'https://rangamsaradhasilks.com'
        for full_url in urls:
            relative_path = full_url[len(domain_prefix):]
            page_resp = self.client.get(relative_path)
            self.assertEqual(
                page_resp.status_code,
                200,
                f"Sitemap URL failed with status {page_resp.status_code}: {relative_path}"
            )


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class PageSEOAndStructuredDataTest(TestCase):
    """
    Tests checking canonical tags, meta titles/descriptions, and JSON-LD structured data
    across Home, Categories, Shop All, Category detail, Product detail, Contact, FAQ, and CMS pages.
    """

    def setUp(self):
        WebsiteSetting.objects.create(website_name="Rangam Saradha Silks")
        ContactInfo.objects.create(
            phone="+91 98765 43210",
            email="contact@rangamsaradhasilks.com",
            address="123 Silk Street, Kanchipuram, Tamil Nadu",
            facebook_url="https://facebook.com/rangamsaradhasilks",
            instagram_url="https://instagram.com/rangamsaradhasilks",
        )
        self.category = Category.objects.create(
            name="Banarasi Silk",
            slug="banarasi-silk",
            is_active=True,
            display_order=1,
            description="Exquisite Banarasi sarees woven with fine zari.",
        )
        self.product = Product.objects.create(
            name="Crimson Banarasi Saree",
            slug="crimson-banarasi-saree",
            sku="BNS-101",
            price=18500.00,
            stock=3,
            is_active=True,
            description="Fine crimson pure silk Banarasi saree.",
        )
        self.product.categories.add(self.category)

        self.cms_about = CMSPage.objects.create(
            title="About Us",
            slug="about-us",
            content="Story of Rangam Saradha Silks.",
        )

        self.faq = FAQ.objects.create(
            question="Are all sarees 100% pure silk?",
            answer="Yes, all our silk sarees are Silk Mark certified.",
            display_order=1,
            is_active=True,
        )

    def test_home_page_seo_and_schema(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://rangamsaradhasilks.com/">', content)

        # WebSite structured data with SearchAction
        self.assertIn('"@type": "WebSite"', content)
        self.assertIn('"@type": "SearchAction"', content)
        self.assertIn('https://rangamsaradhasilks.com/shop/?q={search_term_string}', content)

        # ClothingStore structured data
        self.assertIn('"@type": "ClothingStore"', content)
        self.assertIn('"url": "https://rangamsaradhasilks.com/"', content)

        # FAQ not in footer
        self.assertNotIn(reverse('home:faq'), content)

    def test_categories_page_seo_and_schema(self):
        response = self.client.get(reverse('shop:categories'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://rangamsaradhasilks.com/shop/categories/">', content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"name": "Categories"', content)

        # Category links use canonical URLs
        self.assertIn(self.category.get_absolute_url(), content)

    def test_shop_catalog_seo(self):
        response = self.client.get(reverse('shop:catalog'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://rangamsaradhasilks.com/shop/">', content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"name": "Shop All"', content)

    def test_category_detail_seo_and_canonical(self):
        url = reverse('shop:category_detail', kwargs={'category_slug': self.category.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical tag
        expected_canonical = f'<link rel="canonical" href="https://rangamsaradhasilks.com{url}">'
        self.assertIn(expected_canonical, content)

        # Breadcrumbs
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn(self.category.name, content)

    def test_product_detail_seo_and_schema(self):
        url = self.product.get_absolute_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical tag
        expected_canonical = f'<link rel="canonical" href="https://rangamsaradhasilks.com{url}">'
        self.assertIn(expected_canonical, content)

        # Product schema
        self.assertIn('"@type": "Product"', content)
        self.assertIn(self.product.name, content)
        self.assertIn('"@type": "Offer"', content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn(self.category.name, content)

    def test_contact_page_seo_and_schema(self):
        response = self.client.get(reverse('home:contact'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://rangamsaradhasilks.com/contact/">', content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"name": "Contact Us"', content)

    def test_faq_page_seo_and_schema(self):
        response = self.client.get(reverse('home:faq'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://rangamsaradhasilks.com/faqs/">', content)

        # FAQPage schema
        self.assertIn('"@type": "FAQPage"', content)
        self.assertIn(self.faq.question, content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"name": "Frequently Asked Questions"', content)

    def test_cms_about_us_seo_and_schema(self):
        response = self.client.get(self.cms_about.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Canonical URL
        self.assertIn(f'<link rel="canonical" href="https://rangamsaradhasilks.com{self.cms_about.get_absolute_url()}">', content)

        # BreadcrumbList schema
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"name": "About Us"', content)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class PopupManagementTests(TestCase):
    """
    Tests for the Promotional Popup Management System.
    """

    def setUp(self):
        from home.models import Popup, WebsiteSetting, ContactInfo
        from django.utils import timezone
        from django.contrib.auth import get_user_model
        WebsiteSetting.objects.create(website_name="Rangam Saradha Silks", call_booking_fee=50.00)
        ContactInfo.objects.create(
            phone="+91 98765 43210",
            email="contact@rangamsaradhasilks.com",
            address="123 Silk Street, Kanchipuram, Tamil Nadu",
        )
        User = get_user_model()
        self.user = User.objects.create_user(username='test_caller_popup', email='popup@example.com', password='password123', phone_number='+919876543210')
        self.client.force_login(self.user)

    def test_popup_priority_and_context_processor(self):
        from home.models import Popup
        popup_low = Popup.objects.create(
            title="Low Priority Offer",
            popup_type="OFFER",
            priority=5,
            is_active=True,
        )
        popup_high = Popup.objects.create(
            title="High Priority Festival Offer",
            popup_type="OFFER",
            priority=15,
            is_active=True,
        )

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_popup'], popup_high)
        self.assertIn("High Priority Festival Offer", response.content.decode('utf-8'))
        self.assertNotIn("Low Priority Offer", response.content.decode('utf-8'))

    def test_popup_date_filtering(self):
        from home.models import Popup
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        # Expired popup
        Popup.objects.create(
            title="Expired Popup",
            popup_type="OFFER",
            priority=100,
            is_active=True,
            end_date=now - timedelta(days=1),
        )
        # Future popup
        Popup.objects.create(
            title="Future Popup",
            popup_type="OFFER",
            priority=90,
            is_active=True,
            start_date=now + timedelta(days=2),
        )
        # Active eligible popup
        valid_popup = Popup.objects.create(
            title="Currently Active Popup",
            popup_type="OFFER",
            priority=50,
            is_active=True,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=5),
        )

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_popup'], valid_popup)

    def test_popup_types_rendering(self):
        from home.models import Popup
        coupon_popup = Popup.objects.create(
            title="Exclusive Festive Offer",
            popup_type="OFFER",
            badge_text="FESTIVE 2026",
            coupon_code="FESTIVE15",
            cta_text="Claim Offer",
            cta_link="/shop/",
            is_active=True,
        )
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertIn('rssPromotionalPopup', content)
        self.assertIn('FESTIVE15', content)
        self.assertIn('FESTIVE 2026', content)
        self.assertIn('Claim Offer', content)

    def test_book_call_api_success_and_duplicate(self):
        from django.utils import timezone
        from datetime import timedelta
        from shop.models import CallBooking

        booking_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        post_data = {
            'full_name': 'Meenakshi Sundaram',
            'phone_number': '+91 98765 11223',
            'booking_date': booking_date,
            'time_slot': '11:00 AM - 12:00 PM',
            'saree_preference': 'Bridal Kanchipuram Pure Zari',
        }

        # 1. First booking should succeed
        url = reverse('home:popup_book_call')
        resp = self.client.post(url, data=post_data)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['booking_reference'].startswith('BK-'))

        booking = CallBooking.objects.get(booking_reference=data['booking_reference'])
        self.assertEqual(booking.full_name, 'Meenakshi Sundaram')
        self.assertEqual(booking.saree_preference, 'Bridal Kanchipuram Pure Zari')
        self.assertEqual(float(booking.fee_amount), 50.00)
        self.assertEqual(booking.payment_status, 'PAID')
        self.assertEqual(booking.payment_method, 'UPI')
        self.assertTrue(booking.payment_reference.startswith('TXN-CALL-'))
        self.assertEqual(data['fee_amount'], 50.0)
        self.assertEqual(data['payment_status'], 'PAID')
        self.assertIsNone(booking.product)

        # 2. Duplicate booking within 5 minutes should return friendly message
        dup_resp = self.client.post(url, data=post_data)
        self.assertEqual(dup_resp.status_code, 200)
        dup_data = dup_resp.json()
        self.assertTrue(dup_data['success'])
        self.assertIn('already received', dup_data['message'])

    def test_book_call_api_invalid_date_or_slot(self):
        from django.utils import timezone
        from datetime import timedelta

        past_date = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        url = reverse('home:popup_book_call')

        # Past date
        resp = self.client.post(url, data={
            'full_name': 'Test User',
            'phone_number': '9876543210',
            'booking_date': past_date,
            'time_slot': '10:00 AM - 11:00 AM',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

        # Invalid slot
        future_date = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        resp_slot = self.client.post(url, data={
            'full_name': 'Test User',
            'phone_number': '9876543210',
            'booking_date': future_date,
            'time_slot': 'Invalid Slot',
        })
        self.assertEqual(resp_slot.status_code, 400)
        self.assertFalse(resp_slot.json()['success'])

