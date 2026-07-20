from django.test import TestCase, override_settings
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Order, OrderItem, Product, ProductImage, Category
from .admin import OrderAdmin, OrderItemInline, ProductAdmin

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
class OrderAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.order_admin = OrderAdmin(Order, self.site)
        self.order_item_inline = OrderItemInline(Order, self.site)

        # Create sample Category and Products
        self.category = Category.objects.create(
            name="Saree",
            slug="saree",
            image=SimpleUploadedFile("cat.jpg", b"file_content", content_type="image/jpeg")
        )
        self.product_1 = Product.objects.create(
            name="Deep Maroon Saree",
            slug="deep-maroon-saree",
            sku="DMS-001",
            price=2999.00,
            stock=10
        )
        self.product_1.categories.add(self.category)
        
        self.product_2 = Product.objects.create(
            name="Gold Zari Saree",
            slug="gold-zari-saree",
            sku="GZS-001",
            price=4999.00,
            stock=5
        )
        self.product_2.categories.add(self.category)

        # Create a sample Order
        self.order = Order.objects.create(
            order_number="ORD-1000",
            full_name="Abhi Vigu",
            phone_number="9876543210",
            email="abhi@example.com",
            address_line_1="123 Silk Street",
            city="Kanchipuram",
            state="Tamil Nadu",
            pincode="631501",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=2999.00,
            grand_total=2999.00
        )

    def test_product_thumbnail_no_items(self):
        """
        Verify that an order with no items returns 'No Image'.
        """
        self.assertEqual(self.order_admin.product_thumbnail(self.order), "No Image")

    def test_product_thumbnail_no_images(self):
        """
        Verify that an order with items but whose products have no images returns 'No Image'.
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        self.assertEqual(self.order_admin.product_thumbnail(self.order), "No Image")

    def test_product_thumbnail_with_image(self):
        """
        Verify that a product image thumbnail is rendered correctly when it exists.
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        ProductImage.objects.create(
            product=self.product_1,
            image=SimpleUploadedFile("saree1.jpg", b"image_content", content_type="image/jpeg")
        )
        thumbnail_html = self.order_admin.product_thumbnail(self.order)
        self.assertIn("img", thumbnail_html)
        self.assertIn("saree1.jpg", thumbnail_html)
        self.assertIn('target="_blank"', thumbnail_html)

    def test_product_name_column_single(self):
        """
        Verify that a single ordered product displays its name.
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        self.assertEqual(self.order_admin.product_name_column(self.order), "Deep Maroon Saree")

    def test_product_name_column_multiple(self):
        """
        Verify that multiple ordered products show "+ X more items".
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        OrderItem.objects.create(order=self.order, product=self.product_2, quantity=1, price=4999.00)
        self.assertEqual(self.order_admin.product_name_column(self.order), "Deep Maroon Saree + 1 more items")

    def test_order_status_badge(self):
        """
        Verify badge HTML rendering for different order statuses.
        """
        badge = self.order_admin.order_status_badge(self.order)
        self.assertIn("Pending", badge)
        self.assertIn("#fff8eb", badge)  # Gold/warm yellow
        self.assertIn("#AE6F21", badge)

        self.order.order_status = "CONFIRMED"
        self.order.save()
        badge = self.order_admin.order_status_badge(self.order)
        self.assertIn("Confirmed", badge)
        self.assertIn("#faf5e6", badge)  # Gold/Bronze
        self.assertIn("#8c5d1c", badge)

    def test_payment_status_badge(self):
        """
        Verify badge HTML rendering for different payment statuses.
        """
        badge = self.order_admin.payment_status_badge(self.order)
        self.assertIn("Pending", badge)
        self.assertIn("#fff8eb", badge)

        self.order.payment_status = "PAID"
        self.order.save()
        badge = self.order_admin.payment_status_badge(self.order)
        self.assertIn("Paid", badge)
        self.assertIn("#f1faf5", badge)  # Green
        self.assertIn("#1b8a53", badge)

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
class ProductAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.product_admin = ProductAdmin(Product, self.site)
        self.product = Product.objects.create(
            name="Silk Saree",
            slug="silk-saree",
            sku="SS-001",
            price=3500.00,
            stock=10
        )

    def test_product_image_thumbnail_no_image(self):
        """
        Verify that a product without any image returns 'No Image'.
        """
        self.assertEqual(self.product_admin.product_image_thumbnail(self.product), "No Image")

    def test_product_image_thumbnail_with_image(self):
        """
        Verify that a clickable 60x60 thumbnail of the product is rendered.
        """
        ProductImage.objects.create(
            product=self.product,
            image=SimpleUploadedFile("saree_test.jpg", b"image_content", content_type="image/jpeg")
        )
        thumbnail_html = self.product_admin.product_image_thumbnail(self.product)
        self.assertIn("img", thumbnail_html)
        self.assertIn("saree_test.jpg", thumbnail_html)
        self.assertIn('target="_blank"', thumbnail_html)

class StockManagementAndTotalsTest(TestCase):
    def setUp(self):
        from home.models import WebsiteSetting
        # Setup settings
        self.settings_obj = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silk Sarees",
            tax_percentage=5.00,
            shipping_charge=50.00,
            free_shipping_limit=1000.00
        )
        self.product = Product.objects.create(
            name="Deep Maroon Saree",
            slug="deep-maroon-saree",
            sku="DMS-001",
            price=1000.00,
            discount_percentage=0,
            stock=3,
            is_active=True
        )

    def test_admin_stock_status(self):
        from .admin import ProductAdmin
        from django.contrib.admin.sites import AdminSite
        site = AdminSite()
        product_admin = ProductAdmin(Product, site)
        
        # Test 10 stock -> In Stock
        self.product.stock = 10
        self.product.save()
        status_html = product_admin.stock_status(self.product)
        self.assertIn("In Stock", status_html)
        self.assertIn("#1b8a53", status_html) # Green
        
        # Test 3 stock -> Low Stock
        self.product.stock = 3
        self.product.save()
        status_html = product_admin.stock_status(self.product)
        self.assertIn("Low Stock", status_html)
        self.assertIn("#AE6F21", status_html) # Orange
        
        # Test 0 stock -> Out of Stock
        self.product.stock = 0
        self.product.save()
        status_html = product_admin.stock_status(self.product)
        self.assertIn("Out of Stock", status_html)
        self.assertIn("#AF0446", status_html) # Red

