import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from shop.models import Category, Product

User = get_user_model()


class ProductPriceChangeAdminTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Kanchipuram Silk Sarees", slug="kanchipuram-silk-sarees")
        self.p1 = Product.objects.create(
            name="Kanchi Pure Silk Crimson",
            slug="kanchi-pure-silk-crimson",
            sku="RSS-SA-01",
            price=Decimal("15000.00"),
            offer_price=Decimal("12000.00"),
            discount_percentage=20,
            stock=5,
            is_active=True
        )
        self.p1.categories.add(self.category)

        self.p2 = Product.objects.create(
            name="Kanchi Pure Silk Emerald",
            slug="kanchi-pure-silk-emerald",
            sku="RSS-SA-02",
            price=Decimal("18000.00"),
            offer_price=Decimal("14000.00"),
            discount_percentage=22,
            stock=3,
            is_active=True
        )
        self.p2.categories.add(self.category)

        self.admin_user = User.objects.create_superuser(
            username="admin_price_tester",
            email="admin_price@rangamsaradha.com",
            password="adminpassword123"
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.client.cookies['admin_sessionid'] = self.client.cookies['sessionid'].value

    def test_price_change_page_renders_with_sidebar(self):
        """Ensure the Product Price Change dashboard renders with navigation sidebar and input controls."""
        response = self.client.get('/admin/shop/productpricechange/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Product Price Change')
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, 'id="matchType"')
        self.assertContains(response, 'id="batchRegularPrice"')
        self.assertContains(response, 'RSS-SA-01')
        self.assertContains(response, 'RSS-SA-02')

    def test_filter_by_sku_prefix(self):
        """Ensure searching SKU prefixes returns correct matching products."""
        response = self.client.get('/admin/shop/productpricechange/?sku=RSS-SA-01&match_type=exact')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RSS-SA-01')
        self.assertNotContains(response, 'RSS-SA-02')

    def test_quick_single_update(self):
        """Ensure single row inline price update succeeds."""
        payload = {
            'product_id': self.p1.id,
            'price': '16500.00',
            'offer_price': '13500.00'
        }
        response = self.client.post(
            '/admin/shop/productpricechange/quick-update-single/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        self.p1.refresh_from_db()
        self.assertEqual(self.p1.price, Decimal("16500.00"))
        self.assertEqual(self.p1.offer_price, Decimal("13500.00"))

    def test_batch_update_all_matching(self):
        """Ensure bulk updating all matching products updates prices in database."""
        payload = {
            'update_all_matching': True,
            'search_term': 'RSS-SA',
            'match_type': 'contains',
            'price': '19999.00',
            'offer_price': '15999.00',
            'discount_percentage': 20
        }
        response = self.client.post(
            '/admin/shop/productpricechange/update-batch/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.price, Decimal("19999.00"))
        self.assertEqual(self.p2.price, Decimal("19999.00"))
