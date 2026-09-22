import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from shop.models import Category, Product, BulkStockProduct, BulkStockProductImage

User = get_user_model()

class BulkStockAdminTests(TestCase):
    def setUp(self):
        # Create categories
        self.cat_banarasi = Category.objects.create(name="Banarasi Silk Sarees", slug="banarasi-silk-sarees")
        self.cat_kanchipuram = Category.objects.create(name="Kanchipuram Silk Sarees", slug="kanchipuram-silk-sarees")
        self.cat_chanderi = Category.objects.create(name="Chanderi Sarees", slug="chanderi-sarees")

        # Create staff admin user
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin@rangamsaradha.com",
            password="adminpassword123"
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.client.cookies['admin_sessionid'] = self.client.cookies['sessionid'].value

        # Create regular user (non-staff)
        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="user@test.com",
            password="userpassword123"
        )

    def test_admin_bulk_stock_page_renders(self):
        """Ensure the bulk stock admin dashboard loads properly for staff with nav sidebar and clean state."""
        response = self.client.get('/admin/shop/bulkstockproduct/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk Stock")
        self.assertContains(response, "Add new stock in bulk and publish products when ready.")
        self.assertContains(response, "Total in Bulk")
        # Ensure navigation sidebar is rendered
        self.assertContains(response, 'id="nav-sidebar"')
        # Ensure no fake/default rows exist when bulk stock is empty
        self.assertContains(response, "Bulk Stock is empty")

    def test_save_draft_with_multiple_categories(self):
        """Test saving multiple products with different categories as drafts."""
        payload = {
            "products": [
                {
                    "id": None,
                    "name": "Crimson Kanchipuram Bridal Saree",
                    "category_id": self.cat_kanchipuram.id,
                    "price": 18500,
                    "offer_price": 14999,
                    "discount_percentage": 19,
                    "sku": "KANCHI-CRM-01",
                    "stock": 10,
                    "fabric": "Pure Mulberry Silk",
                    "color": "Crimson Red",
                    "zari_type": "Gold Zari",
                },
                {
                    "id": None,
                    "name": "Royal Blue Banarasi Brocade Saree",
                    "category_id": self.cat_banarasi.id,
                    "price": 22000,
                    "offer_price": 18500,
                    "discount_percentage": 16,
                    "sku": "BANARASI-BLU-02",
                    "stock": 6,
                    "fabric": "Katan Silk",
                    "color": "Royal Blue",
                    "zari_type": "Silver & Gold Zari",
                }
            ]
        }

        response = self.client.post(
            '/admin/shop/bulkstockproduct/save-draft/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["saved_count"], 2)
        self.assertEqual(BulkStockProduct.objects.count(), 2)

        p1 = BulkStockProduct.objects.get(sku="KANCHI-CRM-01")
        self.assertEqual(p1.category, self.cat_kanchipuram)
        self.assertEqual(float(p1.price), 18500.0)

        p2 = BulkStockProduct.objects.get(sku="BANARASI-BLU-02")
        self.assertEqual(p2.category, self.cat_banarasi)
        self.assertEqual(float(p2.offer_price), 18500.0)

    def test_publish_selected_creates_live_products_and_cleans_drafts(self):
        """Test publishing selected draft items to live Products and removing them from BulkStock."""
        draft1 = BulkStockProduct.objects.create(
            name="Emerald Green Kanchipuram",
            category=self.cat_kanchipuram,
            price=25000,
            offer_price=21000,
            discount_percentage=16,
            sku="KANCHI-EMR-10",
            stock=5,
            fabric="Pure Silk",
            color="Emerald Green",
            material="Pure Kanchipuram Silk",
            status="draft",
            created_by=self.admin_user
        )

        draft2 = BulkStockProduct.objects.create(
            name="Pastel Peach Chanderi Saree",
            category=self.cat_chanderi,
            price=8500,
            offer_price=6999,
            discount_percentage=18,
            sku="CHAND-PCH-20",
            stock=12,
            fabric="Chanderi Cotton Silk",
            color="Peach",
            status="draft",
            created_by=self.admin_user
        )

        # Publish only draft1
        payload = {"selected_ids": [draft1.id]}
        response = self.client.post(
            '/admin/shop/bulkstockproduct/publish/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["published_count"], 1)

        # Check live product created
        live_product = Product.objects.filter(sku="KANCHI-EMR-10").first()
        self.assertIsNotNone(live_product)
        self.assertEqual(live_product.name, "Emerald Green Kanchipuram")
        self.assertEqual(float(live_product.price), 25000.0)
        self.assertEqual(float(live_product.offer_price), 21000.0)
        self.assertEqual(live_product.stock, 5)
        self.assertTrue(live_product.categories.filter(id=self.cat_kanchipuram.id).exists())

        # Check draft1 removed from BulkStockProduct, but draft2 remains
        self.assertFalse(BulkStockProduct.objects.filter(id=draft1.id).exists())
        self.assertTrue(BulkStockProduct.objects.filter(id=draft2.id).exists())
        self.assertEqual(BulkStockProduct.objects.count(), 1)

    def test_publish_validation_failure(self):
        """Test publish fails if required fields like product name or price are missing."""
        invalid_draft = BulkStockProduct.objects.create(
            name="",
            category=self.cat_banarasi,
            price=0,
            sku="INVALID-01",
            stock=1,
            created_by=self.admin_user
        )

        payload = {"selected_ids": [invalid_draft.id]}
        response = self.client.post(
            '/admin/shop/bulkstockproduct/publish/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)
        # Ensure draft was not deleted and product was not created
        self.assertEqual(BulkStockProduct.objects.count(), 1)
        self.assertEqual(Product.objects.filter(sku="INVALID-01").count(), 0)

    def test_delete_selected_rows(self):
        """Test deleting selected draft rows."""
        d1 = BulkStockProduct.objects.create(name="Saree 1", price=1000, sku="SKU-1", created_by=self.admin_user)
        d2 = BulkStockProduct.objects.create(name="Saree 2", price=2000, sku="SKU-2", created_by=self.admin_user)

        payload = {"ids": [d1.id]}
        response = self.client.post(
            '/admin/shop/bulkstockproduct/delete-rows/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BulkStockProduct.objects.count(), 1)
        self.assertFalse(BulkStockProduct.objects.filter(id=d1.id).exists())
        self.assertTrue(BulkStockProduct.objects.filter(id=d2.id).exists())

    def test_clear_all_drafts(self):
        """Test clearing all drafts."""
        BulkStockProduct.objects.create(name="Saree A", price=1000, sku="SKU-A", created_by=self.admin_user)
        BulkStockProduct.objects.create(name="Saree B", price=2000, sku="SKU-B", created_by=self.admin_user)
        self.assertEqual(BulkStockProduct.objects.count(), 2)

        response = self.client.post('/admin/shop/bulkstockproduct/clear-all/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BulkStockProduct.objects.count(), 0)

    def test_image_upload_endpoint(self):
        """Test staging image upload via the dedicated endpoint."""
        draft = BulkStockProduct.objects.create(name="Image Test Saree", price=5000, sku="IMG-001", created_by=self.admin_user)

        dummy_image = SimpleUploadedFile(
            name="test_saree.jpg",
            content=b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b",
            content_type="image/jpeg"
        )

        response = self.client.post(
            '/admin/shop/bulkstockproduct/upload-image/',
            data={'row_id': draft.id, 'image': dummy_image, 'is_primary': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue("image_url" in data)

        draft.refresh_from_db()
        self.assertTrue(bool(draft.image))

    def test_non_staff_forbidden(self):
        """Non-staff users should not be allowed to access bulk stock admin endpoints."""
        non_staff_client = Client()
        non_staff_client.login(username="regular_user", password="userpassword123")

        response = non_staff_client.get('/admin/shop/bulkstockproduct/')
        # Should redirect to admin login or return 302
        self.assertIn(response.status_code, [302, 403])
