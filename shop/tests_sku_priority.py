from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from home.models import WebsiteSetting
from shop.models import Category, Product


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
class SkuPriorityOrderingTestCase(TestCase):
    def setUp(self):
        # 1. Setup WebsiteSetting
        self.settings = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silks",
            priority_sku_prefixes="RSS-GB, KJM-SUB"
        )

        # 2. Setup Category
        self.category = Category.objects.create(name="Kanchipuram Silk", slug="kanchipuram-silk")

        # 3. Create products with prefixes specified by user
        # Group 1: RSS-GB prefix
        self.p_rss_1 = Product.objects.create(
            name="RSS Green Brocade Saree 006",
            slug="rss-green-brocade-006",
            sku="RSS-GB-006",
            price=Decimal("12000.00"),
            offer_price=Decimal("12000.00"),
            stock=10,
            is_active=True,
            is_trending=True,
        )
        self.p_rss_1.categories.add(self.category)

        self.p_rss_2 = Product.objects.create(
            name="RSS Gold Brocade Saree 011",
            slug="rss-gold-brocade-011",
            sku="RSS-GB-011",
            price=Decimal("8000.00"),
            offer_price=Decimal("8000.00"),
            stock=5,
            is_active=True,
            is_trending=False,
        )
        self.p_rss_2.categories.add(self.category)

        # Group 2: KJM-SUB prefix
        self.p_kjm_1 = Product.objects.create(
            name="KJM Subha Silk 027",
            slug="kjm-subha-silk-027",
            sku="KJM-SUB-027",
            price=Decimal("15000.00"),
            offer_price=Decimal("15000.00"),
            stock=8,
            is_active=True,
            is_trending=False,
        )
        self.p_kjm_1.categories.add(self.category)

        self.p_kjm_2 = Product.objects.create(
            name="KJM Subha Silk 028",
            slug="kjm-subha-silk-028",
            sku="KJM-SUB-028",
            price=Decimal("10000.00"),
            offer_price=Decimal("10000.00"),
            stock=6,
            is_active=True,
            is_trending=True,
        )
        self.p_kjm_2.categories.add(self.category)

        # Group 3: Other prefixes (unprioritized)
        self.p_other_1 = Product.objects.create(
            name="Banarasi Royal Blue",
            slug="banarasi-royal-blue",
            sku="BAN-BLU-001",
            price=Decimal("6000.00"),
            offer_price=Decimal("6000.00"),
            stock=4,
            is_active=True,
            is_trending=False,
        )
        self.p_other_1.categories.add(self.category)

        self.p_other_2 = Product.objects.create(
            name="Dharmavaram Pure Silk",
            slug="dharmavaram-pure-silk",
            sku="DMS-055",
            price=Decimal("18000.00"),
            offer_price=Decimal("18000.00"),
            stock=12,
            is_active=True,
            is_trending=True,
        )
        self.p_other_2.categories.add(self.category)

    def test_get_priority_sku_prefixes_helper(self):
        """WebsiteSetting parses comma-separated SKU prefixes cleanly."""
        self.settings.priority_sku_prefixes = " RSS-GB ,  KJM-SUB , RSS-GB , , OTHER "
        self.settings.save()
        prefixes = self.settings.get_priority_sku_prefixes()
        self.assertEqual(prefixes, ["RSS-GB", "KJM-SUB", "OTHER"])

    def test_catalog_ordering_rss_gb_then_kjm_sub(self):
        """
        When setting is 'RSS-GB, KJM-SUB':
        1. All RSS-GB-* products appear first
        2. All KJM-SUB-* products appear second
        3. All other products appear after prioritized products
        """
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'))
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        skus = [p.sku for p in products]

        # First 2 must be RSS-GB products
        self.assertEqual(set(skus[:2]), {"RSS-GB-006", "RSS-GB-011"})
        # Next 2 must be KJM-SUB products
        self.assertEqual(set(skus[2:4]), {"KJM-SUB-027", "KJM-SUB-028"})
        # Last 2 must be unprioritized products
        self.assertEqual(set(skus[4:]), {"BAN-BLU-001", "DMS-055"})

    def test_catalog_ordering_change_admin_setting(self):
        """
        When admin changes setting to 'KJM-SUB, RSS-GB':
        1. KJM-SUB-* products appear first
        2. RSS-GB-* products appear second
        3. Unprioritized products appear last
        """
        self.settings.priority_sku_prefixes = "KJM-SUB, RSS-GB"
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'))
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        skus = [p.sku for p in products]

        # First 2 must be KJM-SUB products
        self.assertEqual(set(skus[:2]), {"KJM-SUB-027", "KJM-SUB-028"})
        # Next 2 must be RSS-GB products
        self.assertEqual(set(skus[2:4]), {"RSS-GB-006", "RSS-GB-011"})
        # Last 2 must be unprioritized products
        self.assertEqual(set(skus[4:]), {"BAN-BLU-001", "DMS-055"})

    def test_price_low_to_high_sorts_globally(self):
        """
        Price Low to High sorting sorts all products strictly by price ascending:
        BAN-BLU-001 (₹6,000) -> RSS-GB-011 (₹8,000) -> KJM-SUB-028 (₹10,000) ->
        RSS-GB-006 (₹12,000) -> KJM-SUB-027 (₹15,000) -> DMS-055 (₹18,000).
        """
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'), {'sort': 'price_low'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        skus = [p.sku for p in products]

        self.assertEqual(skus, [
            "BAN-BLU-001",  # ₹6,000
            "RSS-GB-011",   # ₹8,000
            "KJM-SUB-028",  # ₹10,000
            "RSS-GB-006",   # ₹12,000
            "KJM-SUB-027",  # ₹15,000
            "DMS-055",      # ₹18,000
        ])

    def test_price_high_to_low_sorts_globally(self):
        """
        Price High to Low sorting sorts all products strictly by price descending:
        DMS-055 (₹18,000) -> KJM-SUB-027 (₹15,000) -> RSS-GB-006 (₹12,000) ->
        KJM-SUB-028 (₹10,000) -> RSS-GB-011 (₹8,000) -> BAN-BLU-001 (₹6,000).
        """
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'), {'sort': 'price_high'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        skus = [p.sku for p in products]

        self.assertEqual(skus, [
            "DMS-055",      # ₹18,000
            "KJM-SUB-027",  # ₹15,000
            "RSS-GB-006",   # ₹12,000
            "KJM-SUB-028",  # ₹10,000
            "RSS-GB-011",   # ₹8,000
            "BAN-BLU-001",  # ₹6,000
        ])

    def test_popularity_sort_globally(self):
        """
        Popularity sorting sorts trending products first globally across the catalog.
        """
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'), {'sort': 'popular'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        
        # All trending products appear before non-trending products
        trending_flags = [p.is_trending for p in products]
        self.assertTrue(all(trending_flags[:3]))
        self.assertFalse(any(trending_flags[3:]))

    def test_empty_priority_setting_falls_back_to_standard_sort(self):
        """If no priority SKU prefixes are configured, standard sorting applies."""
        self.settings.priority_sku_prefixes = ""
        self.settings.save()

        response = self.client.get(reverse('shop:catalog'), {'sort': 'price_low'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        prices = [p.offer_price for p in products]
        self.assertEqual(prices, sorted(prices))

    def test_sku_is_displayed_on_frontend_product_card_and_detail(self):
        """
        SKU number is displayed on product cards and product detail page.
        """
        # Catalog page test
        response_catalog = self.client.get(reverse('shop:catalog'))
        self.assertEqual(response_catalog.status_code, 200)
        content_catalog = response_catalog.content.decode('utf-8')
        self.assertIn("SKU: RSS-GB-006", content_catalog)
        self.assertIn("SKU: KJM-SUB-027", content_catalog)

        # Product detail page test
        response_detail = self.client.get(reverse('shop:product_detail', kwargs={'slug': self.p_rss_1.slug}))
        self.assertEqual(response_detail.status_code, 200)
        content_detail = response_detail.content.decode('utf-8')
        self.assertIn("SKU: RSS-GB-006", content_detail)
        self.assertIn('class="showcase-sku"', content_detail)

    def test_database_sku_values_unmodified(self):
        """Original SKU values stored in the database remain intact."""
        self.p_rss_1.refresh_from_db()
        self.p_kjm_1.refresh_from_db()
        self.assertEqual(self.p_rss_1.sku, "RSS-GB-006")
        self.assertEqual(self.p_kjm_1.sku, "KJM-SUB-027")

    def test_filters_with_price_sorting(self):
        """Filters (such as min_price/max_price) operate correctly alongside price sorting."""
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        # Filter products >= 10,000 sorted price_low:
        # Matches KJM-SUB-028 (10,000), RSS-GB-006 (12,000), KJM-SUB-027 (15,000), DMS-055 (18,000)
        response = self.client.get(reverse('shop:catalog'), {'min_price': '10000', 'sort': 'price_low'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        skus = [p.sku for p in products]

        self.assertEqual(skus, [
            "KJM-SUB-028",  # 10,000
            "RSS-GB-006",   # 12,000
            "KJM-SUB-027",  # 15,000
            "DMS-055",      # 18,000
        ])

    def test_pagination_preserves_sku_priority_order_on_default(self):
        """Pagination slices the prioritized queryset properly across pages on default view."""
        from django.core.paginator import Paginator
        self.settings.priority_sku_prefixes = "RSS-GB, KJM-SUB"
        self.settings.save()

        from shop.views import apply_sku_priority_and_sorting
        qs = Product.objects.filter(is_active=True, stock__gt=0)
        sorted_qs = apply_sku_priority_and_sorting(qs, sort_by='new', site_settings=self.settings)

        paginator = Paginator(sorted_qs, 2)  # 2 items per page
        page1 = paginator.get_page(1)
        page2 = paginator.get_page(2)
        page3 = paginator.get_page(3)

        self.assertEqual(set(p.sku for p in page1), {"RSS-GB-006", "RSS-GB-011"})
        self.assertEqual(set(p.sku for p in page2), {"KJM-SUB-027", "KJM-SUB-028"})
        self.assertEqual(set(p.sku for p in page3), {"BAN-BLU-001", "DMS-055"})

