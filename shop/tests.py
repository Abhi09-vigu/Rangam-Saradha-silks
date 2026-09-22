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
        Verify that a 60x60 thumbnail of the product is rendered.
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        ProductImage.objects.create(
            product=self.product_1,
            image=SimpleUploadedFile("saree1.jpg", b"image_content", content_type="image/jpeg")
        )
        thumbnail_html = self.order_admin.product_thumbnail(self.order)
        self.assertIn("img", thumbnail_html)
        self.assertIn("saree1.jpg", thumbnail_html)

    def test_product_name_column_single(self):
        """
        Verify that a single ordered product displays its name.
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        html = self.order_admin.product_name_column(self.order)
        self.assertEqual(html, "Deep Maroon Saree")

    def test_product_name_column_multiple(self):
        """
        Verify that multiple ordered products show "+ X more items".
        """
        OrderItem.objects.create(order=self.order, product=self.product_1, quantity=1, price=2999.00)
        OrderItem.objects.create(order=self.order, product=self.product_2, quantity=1, price=4999.00)
        html = self.order_admin.product_name_column(self.order)
        self.assertEqual(html, "Deep Maroon Saree + 1 more items")

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

    def test_order_admin_separation_and_permissions(self):
        """
        Verify that OrderAdmin has correct readonly fields, fieldsets, and custom choices,
        and that inline order items cannot be added or deleted.
        """
        # 1. Verify readonly fields (system metadata and financial amounts are locked, customer & billing info are editable)
        self.assertIn('order_number', self.order_admin.readonly_fields)
        self.assertIn('subtotal', self.order_admin.readonly_fields)
        self.assertIn('tax_amount', self.order_admin.readonly_fields)
        self.assertIn('grand_total', self.order_admin.readonly_fields)
        self.assertNotIn('full_name', self.order_admin.readonly_fields)
        self.assertNotIn('order_status', self.order_admin.readonly_fields)
        self.assertNotIn('payment_status', self.order_admin.readonly_fields)

        # 2. Verify fieldsets setup (gst_number is removed from editable customer fields, tracking fields added)
        fieldsets_dict = dict(self.order_admin.fieldsets)
        self.assertIn('Customer & Billing Details', fieldsets_dict)
        self.assertIn('Shipment & Tracking', fieldsets_dict)
        self.assertIn('Invoice & Financials (Locked)', fieldsets_dict)
        customer_fields = fieldsets_dict['Customer & Billing Details']['fields']
        self.assertNotIn('gst_number', customer_fields)
        tracking_fields = fieldsets_dict['Shipment & Tracking']['fields']
        self.assertIn('tracking_link', tracking_fields)
        self.assertIn('tracking_number', tracking_fields)

        # 3. Verify restricted choices in formfield_for_choice_field
        from django.db import models
        order_status_field = Order._meta.get_field('order_status')
        form_field = self.order_admin.formfield_for_choice_field(order_status_field, None)
        choices = [c[0] for c in form_field.choices]
        self.assertIn('PENDING', choices)
        self.assertIn('DELIVERED', choices)
        self.assertNotIn('RETURNED', choices)

        payment_status_field = Order._meta.get_field('payment_status')
        form_field_payment = self.order_admin.formfield_for_choice_field(payment_status_field, None)
        payment_choices = [c[0] for c in form_field_payment.choices]
        self.assertIn('PENDING', payment_choices)
        self.assertIn('REFUNDED', payment_choices)

        # 4. Verify OrderItemInline prevents adding/deleting to protect order amounts
        from django.test import RequestFactory
        from django.contrib.auth import get_user_model
        rf = RequestFactory()
        req = rf.get('/')
        User = get_user_model()
        req.user = User.objects.create_superuser(username='superadmin_perm_test', email='adm@test.com', password='password123')
        self.assertFalse(self.order_item_inline.has_add_permission(req, None))
        self.assertFalse(self.order_item_inline.has_delete_permission(req, None))

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

    def test_product_admin_separation_and_offer_price(self):
        """
        Verify that ProductAdmin fieldsets are configured correctly,
        and that a custom offer_price is saved while a blank one is automatically calculated.
        """
        from decimal import Decimal
        # 1. Verify fieldsets setup
        fieldsets_names = [f[0] for f in self.product_admin.fieldsets]
        self.assertIn('Basic Information', fieldsets_names)
        self.assertIn('Pricing & Inventory', fieldsets_names)
        self.assertIn('Product Description', fieldsets_names)

        # 2. Test saving a custom offer price
        product_custom = Product.objects.create(
            name="Custom Price Saree",
            slug="custom-price-saree",
            sku="CPS-001",
            price=3000.00,
            discount_percentage=0,
            offer_price=2500.00,
            stock=10
        )
        self.assertEqual(product_custom.offer_price, Decimal('2500.00'))

        # 3. Test automatic calculation of offer price when left blank
        product_auto = Product.objects.create(
            name="Auto Price Saree",
            slug="auto-price-saree",
            sku="APS-001",
            price=3000.00,
            discount_percentage=10,
            offer_price=None,
            stock=10
        )
        self.assertEqual(product_auto.offer_price, Decimal('2700.00'))

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

class OrderEmailSignalsTest(TestCase):
    def setUp(self):
        from home.models import WebsiteSetting
        # Setup settings
        self.settings_obj = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silk Sarees",
            tax_percentage=5.00,
            shipping_charge=50.00,
            free_shipping_limit=1000.00
        )
        
        # Create categories and products
        self.category = Category.objects.create(name="Saree", slug="saree")
        self.product = Product.objects.create(
            name="Deep Maroon Saree",
            slug="deep-maroon-saree",
            sku="DMS-001",
            price=1000.00,
            stock=10,
            is_active=True
        )

    def test_order_creation_triggers_confirmation_email(self):
        from django.core import mail
        import time
        # Clear outbox before test
        mail.outbox = []
        
        # Create an Order
        order = Order.objects.create(
            order_number="ORD-TEST-101",
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
            subtotal=1000.00,
            grand_total=1050.00
        )
        
        # Give thread 0.1s to finish sending
        time.sleep(0.1)
        
        # Verify confirmation email was queued
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Thank you for your order!", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["abhi@example.com"])

    def test_order_status_update_triggers_status_email(self):
        from django.core import mail
        import time
        # Create order first
        order = Order.objects.create(
            order_number="ORD-TEST-102",
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
            subtotal=1000.00,
            grand_total=1050.00
        )
        
        time.sleep(0.1)
        mail.outbox = [] # Clear outbox after creation email
        
        # Update order status
        order.order_status = "SHIPPED"
        order.save()
        
        time.sleep(0.1)
        
        # Verify status update email was queued
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Status Update: Shipped", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["abhi@example.com"])


class CatalogSkuFilterTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Silk Sarees", slug="silk-sarees")
        self.product_1 = Product.objects.create(
            name="Kanjeevaram Gold Border Saree",
            slug="kanjeevaram-gold-border",
            sku="KJB-101",
            price=12000.00,
            stock=8,
            is_active=True
        )
        self.product_1.categories.add(self.category)

        self.product_2 = Product.objects.create(
            name="Banarasi Brocade Silk Saree",
            slug="banarasi-brocade-silk",
            sku="BBS-202",
            price=18000.00,
            stock=4,
            is_active=True
        )
        self.product_2.categories.add(self.category)

    def test_catalog_filter_by_exact_sku(self):
        from django.urls import reverse
        response = self.client.get(reverse('shop:catalog'), {'sku': 'KJB-101'})
        self.assertEqual(response.status_code, 200)
        product_list = list(response.context['products'])
        self.assertEqual(len(product_list), 1)
        self.assertEqual(product_list[0].sku, 'KJB-101')
        self.assertContains(response, 'KJB-101')

    def test_catalog_filter_by_partial_sku(self):
        from django.urls import reverse
        response = self.client.get(reverse('shop:catalog'), {'sku': 'bbs'})
        self.assertEqual(response.status_code, 200)
        product_list = list(response.context['products'])
        self.assertEqual(len(product_list), 1)
        self.assertEqual(product_list[0].sku, 'BBS-202')

    def test_sku_autocomplete_api(self):
        from django.urls import reverse
        response = self.client.get(reverse('shop:sku_autocomplete_api'), {'q': 'KJB'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['sku'], 'KJB-101')

    def test_main_query_includes_sku(self):
        from django.urls import reverse
        response = self.client.get(reverse('shop:catalog'), {'q': 'BBS-202'})
        self.assertEqual(response.status_code, 200)
        product_list = list(response.context['products'])
        self.assertEqual(len(product_list), 1)
        self.assertEqual(product_list[0].sku, 'BBS-202')


class MonthlySalesReportTest(TestCase):
    def setUp(self):
        from accounts.models import CustomUser
        self.admin_user = CustomUser.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="adminpassword123"
        )
        self.category = Category.objects.create(name="Kanjivaram", slug="kanjivaram")
        self.product = Product.objects.create(
            name="Bridal Red Kanjivaram Saree",
            slug="bridal-red-kanjivaram-saree",
            sku="BRK-999",
            price=12500.00,
            stock=15
        )
        self.product.categories.add(self.category)

        # Create order in September 2026
        self.order = Order.objects.create(
            order_number="ORD-SEP-2026",
            full_name="Lakshmi Narayanan",
            phone_number="9876543219",
            email="lakshmi@example.com",
            address_line_1="45 Temple Street",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="ONLINE",
            payment_status="PAID",
            order_status="DELIVERED",
            subtotal=12500.00,
            grand_total=12500.00
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=12500.00
        )

    def test_generate_monthly_sales_excel_direct(self):
        import io
        import openpyxl
        from shop.reports import generate_monthly_sales_excel
        from django.utils import timezone

        now = timezone.localtime(self.order.created_at)
        response = generate_monthly_sales_excel(now.year, now.month)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('.xlsx', response['Content-Disposition'])

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertTrue(len(wb.sheetnames) > 0)
        ws = wb.active
        self.assertEqual(ws["A1"].value, "RANGAM SARADHA SILK SAREES")
        self.assertIn("MONTHLY REVENUE & SALES REPORT", ws["A2"].value)

        # Find our product row in data table
        found_product = False
        for row in range(9, ws.max_row + 1):
            if ws.cell(row=row, column=3).value == "Bridal Red Kanjivaram Saree":
                found_product = True
                self.assertEqual(ws.cell(row=row, column=4).value, "BRK-999")
                self.assertEqual(ws.cell(row=row, column=6).value, "Lakshmi Narayanan")
                self.assertEqual(ws.cell(row=row, column=7).value, "9876543219")
                self.assertEqual(ws.cell(row=row, column=9).value, 2)
                self.assertEqual(ws.cell(row=row, column=10).value, 12500.0)
                self.assertEqual(ws.cell(row=row, column=11).value, 25000.0)
                break
        self.assertTrue(found_product)

    def test_admin_monthly_sales_report_permission(self):
        from django.urls import reverse
        from django.utils import timezone

        now = timezone.localtime(timezone.now())
        url = f"/admin/shop/order/monthly-report/?month={now.month}&year={now.year}"

        # Anonymous user should be redirected to login
        anon_resp = self.client.get(url)
        self.assertEqual(anon_resp.status_code, 302)

        # Staff admin user should get 200 Excel download
        self.client.force_login(self.admin_user)
        self.client.cookies['admin_sessionid'] = self.client.cookies['sessionid'].value
        auth_resp = self.client.get(url)
        self.assertEqual(auth_resp.status_code, 200)
        self.assertEqual(
            auth_resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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
class OutOfStockVisibilityAndAdminTest(TestCase):
    def setUp(self):
        from accounts.models import CustomUser, Wishlist
        from shop.models import Category, Product, Cart, CartItem
        from django.contrib.admin.sites import AdminSite
        from shop.admin import ProductAdmin

        self.site = AdminSite()
        self.product_admin = ProductAdmin(Product, self.site)

        self.user = CustomUser.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            phone_number="9876543210",
            password="testpassword123"
        )
        self.admin_user = CustomUser.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            phone_number="9876543211",
            password="testpassword123"
        )

        self.category = Category.objects.create(name="Kanjivaram", slug="kanjivaram")

        self.in_stock_product = Product.objects.create(
            name="In Stock Saree",
            slug="in-stock-saree",
            sku="ISS-001",
            price=3000.00,
            stock=8,
            is_active=True
        )
        self.in_stock_product.categories.add(self.category)

        self.out_of_stock_product = Product.objects.create(
            name="Out Of Stock Saree",
            slug="out-of-stock-saree",
            sku="OSS-001",
            price=4500.00,
            stock=0,
            is_active=True
        )
        self.out_of_stock_product.categories.add(self.category)

    def test_out_of_stock_hidden_from_catalog(self):
        """Verify out of stock product is completely removed from website catalog."""
        resp = self.client.get('/shop/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "In Stock Saree")
        self.assertNotContains(resp, "Out Of Stock Saree")

    def test_out_of_stock_hidden_from_category_page(self):
        """Verify out of stock product is not shown in category detail page."""
        resp = self.client.get(f'/shop/category/{self.category.slug}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "In Stock Saree")
        self.assertNotContains(resp, "Out Of Stock Saree")

    def test_out_of_stock_inaccessible_on_detail_page(self):
        """Verify direct URL to out of stock product returns 404 on the website."""
        resp = self.client.get(f'/shop/product/{self.out_of_stock_product.slug}/')
        self.assertEqual(resp.status_code, 404)

        # In-stock product is accessible
        in_stock_resp = self.client.get(f'/shop/product/{self.in_stock_product.slug}/')
        self.assertEqual(in_stock_resp.status_code, 200)

    def test_out_of_stock_cannot_be_added_to_cart(self):
        """Verify customers cannot add an out of stock product to cart."""
        resp = self.client.post(f'/shop/cart/add/{self.out_of_stock_product.id}/', {'quantity': 1})
        self.assertEqual(resp.status_code, 404)

    def test_out_of_stock_auto_removed_from_cart(self):
        """Verify cart cleanses out of stock items automatically when viewing cart."""
        from shop.models import Cart, CartItem
        self.client.force_login(self.user)
        cart = Cart.objects.create(user=self.user)
        item_out = CartItem.objects.create(cart=cart, product=self.out_of_stock_product, quantity=1)
        item_in = CartItem.objects.create(cart=cart, product=self.in_stock_product, quantity=1)

        resp = self.client.get('/shop/cart/')
        self.assertEqual(resp.status_code, 200)
        # Warning alert notifies user that the out of stock item was removed
        self.assertContains(resp, "became out of stock and were removed from your cart: Out Of Stock Saree")
        self.assertContains(resp, "In Stock Saree")
        # Ensure the out-of-stock item is removed from the cart table form
        self.assertNotContains(resp, f"/shop/cart/update/{item_out.id}/")
        self.assertContains(resp, f"/shop/cart/update/{item_in.id}/")
        # Ensure the item was actually purged from database CartItem
        self.assertFalse(CartItem.objects.filter(cart=cart, product=self.out_of_stock_product).exists())
        self.assertTrue(CartItem.objects.filter(cart=cart, product=self.in_stock_product).exists())

    def test_out_of_stock_auto_removed_from_wishlist(self):
        """Verify wishlist cleanses and does not display out of stock products."""
        from accounts.models import Wishlist
        self.client.force_login(self.user)
        Wishlist.objects.create(user=self.user, product=self.out_of_stock_product)
        Wishlist.objects.create(user=self.user, product=self.in_stock_product)

        resp = self.client.get('/accounts/wishlist/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Out Of Stock Saree")
        self.assertContains(resp, "In Stock Saree")
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=self.out_of_stock_product).exists())

    def test_admin_shows_out_of_stock_product_and_filter(self):
        """Verify admin panel lists out of stock products and displays 'Out of Stock' status."""
        # Status HTML in ProductAdmin
        status_html = self.product_admin.stock_status(self.out_of_stock_product)
        self.assertIn("Out of Stock", status_html)

        # Admin Changelist has both in-stock and out-of-stock products
        self.client.force_login(self.admin_user)
        self.client.cookies['admin_sessionid'] = self.client.cookies['sessionid'].value
        resp = self.client.get('/admin/shop/product/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Out Of Stock Saree")
        self.assertContains(resp, "In Stock Saree")
        self.assertContains(resp, "Out of Stock")

        # Admin filter by out of stock
        filter_resp = self.client.get('/admin/shop/product/?stock_status=out_of_stock')
        self.assertEqual(filter_resp.status_code, 200)
        self.assertContains(filter_resp, "Out Of Stock Saree")
        self.assertNotContains(filter_resp, "In Stock Saree")

    def test_admin_dashboard_out_of_stock_count(self):
        """Verify admin dashboard context contains out_of_stock_products_count."""
        from rangam_saradha_silk.admin import CustomAdminSite
        custom_site = CustomAdminSite()
        from django.test.client import RequestFactory
        request = RequestFactory().get('/admin/')
        request.user = self.admin_user
        response = custom_site.index(request)
        self.assertIn('out_of_stock_products_count', response.context_data)
        self.assertEqual(response.context_data['out_of_stock_products_count'], 1)




