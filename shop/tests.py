from django.test import TestCase, override_settings
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Order, OrderItem, Product, ProductImage, Category
from .admin import OrderAdmin, OrderItemInline

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
        self.assertIn("#fef3c7", badge)  # Yellow

        self.order.order_status = "CONFIRMED"
        self.order.save()
        badge = self.order_admin.order_status_badge(self.order)
        self.assertIn("Confirmed", badge)
        self.assertIn("#dbeafe", badge)  # Blue

    def test_payment_status_badge(self):
        """
        Verify badge HTML rendering for different payment statuses.
        """
        badge = self.order_admin.payment_status_badge(self.order)
        self.assertIn("Pending", badge)
        self.assertIn("#fef3c7", badge)

        self.order.payment_status = "PAID"
        self.order.save()
        badge = self.order_admin.payment_status_badge(self.order)
        self.assertIn("Paid", badge)
        self.assertIn("#dcfce7", badge)
