from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.core import mail
from django.contrib.auth import get_user_model
from django.urls import reverse
from home.models import WebsiteSetting
from shop.models import Product, Category, Order, OrderItem, Cart, CartItem
from accounts.models import Address
from shop.pricing import calculate_order_pricing
from shop.email_service import send_owner_order_notification_email

User = get_user_model()

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
class PricingCodGstTestCase(TestCase):
    def setUp(self):
        # Configure WebsiteSetting singleton
        self.settings = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silks",
            currency="₹",
            gst_number="33AAAAA0000A1Z5",
            shipping_charge=Decimal('0.00'),
            free_shipping_limit=Decimal('0.00'),
            tax_percentage=Decimal('5.00')
        )
        
        self.user = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="testpassword123",
            phone_number="+919876543210"
        )
        
        self.category = Category.objects.create(name="Pure Silk", slug="pure-silk")
        
        # Product 1: ₹1,500
        self.prod_1500 = Product.objects.create(
            name="Soft Silk Saree 1500",
            slug="soft-silk-1500",
            sku="SS-1500",
            price=Decimal('1500.00'),
            stock=10,
            is_active=True
        )
        self.prod_1500.categories.add(self.category)
        
        # Product 2: ₹2,000
        self.prod_2000 = Product.objects.create(
            name="Kanchipuram Silk 2000",
            slug="kanchi-silk-2000",
            sku="KS-2000",
            price=Decimal('2000.00'),
            stock=10,
            is_active=True
        )
        self.prod_2000.categories.add(self.category)
        
        # Product 3: ₹2,500
        self.prod_2500 = Product.objects.create(
            name="Bridal Silk 2500",
            slug="bridal-silk-2500",
            sku="BS-2500",
            price=Decimal('2500.00'),
            stock=10,
            is_active=True
        )
        self.prod_2500.categories.add(self.category)
        
        # Product 4: ₹900 (2 items = 1800)
        self.prod_900 = Product.objects.create(
            name="Mysore Silk 900",
            slug="mysore-silk-900",
            sku="MS-900",
            price=Decimal('900.00'),
            stock=10,
            is_active=True
        )
        self.prod_900.categories.add(self.category)
        
        # Product 5: ₹1,100 (2 items = 2200)
        self.prod_1100 = Product.objects.create(
            name="Tussar Silk 1100",
            slug="tussar-silk-1100",
            sku="TS-1100",
            price=Decimal('1100.00'),
            stock=10,
            is_active=True
        )
        self.prod_1100.categories.add(self.category)
        
        self.address = Address.objects.create(
            user=self.user,
            full_name="Abhi Vigu",
            phone_number="9876543210",
            address_line_1="10 Main Silk Road",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            is_default=True
        )

    def test_case_a_cart_1500_cod_selected(self):
        """Case A: Cart with item ₹1,500, COD requested -> COD is disabled, 0 COD charge added, final total = ₹1,575."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('1500.00'),
            payment_method='COD',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['subtotal'], Decimal('1575.00'))
        self.assertEqual(pricing['grand_total'], Decimal('1575.00'))
        # 5% GST added: 1500 * 0.05 = 75.00
        self.assertEqual(pricing['tax_amount'], Decimal('75.00'))
        self.assertEqual(pricing['cgst_amount'], Decimal('37.50'))
        self.assertEqual(pricing['sgst_amount'], Decimal('37.50'))

    def test_case_b_cart_1500_online_selected(self):
        """Case B: Cart with item ₹1,500, Online Payment selected -> 5% GST directly added (₹75), ₹0 COD charge, final total = ₹1,575."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('1500.00'),
            payment_method='ONLINE',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['subtotal'], Decimal('1575.00'))
        self.assertEqual(pricing['grand_total'], Decimal('1575.00'))
        self.assertEqual(pricing['effective_payment_method'], 'ONLINE')

    def test_case_c_cart_2000_cod_available_free(self):
        """Case C: Cart with item ₹2,000 -> 5% GST added (₹100), Subtotal = ₹2,100 -> ₹0 COD charge, Total = ₹2,100."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('2000.00'),
            payment_method='COD',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['effective_payment_method'], 'ONLINE')
        self.assertEqual(pricing['subtotal'], Decimal('2100.00'))
        self.assertEqual(pricing['grand_total'], Decimal('2100.00'))

    def test_case_d_cart_2500_cod_available_free(self):
        """Case D: Cart with item ₹2,500 -> 5% GST added (₹125), Subtotal = ₹2,625 -> ₹0 COD charge, Total = ₹2,625."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('2500.00'),
            payment_method='COD',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['effective_payment_method'], 'ONLINE')
        self.assertEqual(pricing['subtotal'], Decimal('2625.00'))
        self.assertEqual(pricing['grand_total'], Decimal('2625.00'))

    def test_case_e_cart_multiple_items_1800_cod_available(self):
        """Case E: Cart with multiple items totaling ₹1,800 -> 5% GST added (₹90), Subtotal = ₹1,890. COD charge = ₹0, Total = ₹1,890."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('1800.00'),
            payment_method='COD',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['subtotal'], Decimal('1890.00'))
        self.assertEqual(pricing['grand_total'], Decimal('1890.00'))
        self.assertEqual(pricing['effective_payment_method'], 'ONLINE')

    def test_case_f_cart_multiple_items_2200_cod_available_free(self):
        """Case F: Cart with multiple items totaling ₹2,200 -> 5% GST added (₹110), Subtotal = ₹2,310 -> ₹0 COD charge, Total = ₹2,310."""
        pricing = calculate_order_pricing(
            subtotal=Decimal('2200.00'),
            payment_method='COD',
            settings_obj=self.settings
        )
        self.assertFalse(pricing['is_cod_eligible'])
        self.assertEqual(pricing['cod_charge'], Decimal('0.00'))
        self.assertEqual(pricing['effective_payment_method'], 'ONLINE')
        self.assertEqual(pricing['subtotal'], Decimal('2310.00'))
        self.assertEqual(pricing['grand_total'], Decimal('2310.00'))

    def test_case_g_admin_owner_email_contents(self):
        """Case G: Verify admin/owner email contains full 5% GST accounting details (CGST 2.5% + SGST 2.5%, GST amount, GSTIN) and COD charge."""
        order = Order.objects.create(
            user=self.user,
            order_number="RS-TEST1234",
            full_name="Abhi Vigu",
            phone_number="9876543210",
            email="customer@example.com",
            address_line_1="10 Main Silk Road",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=Decimal('1500.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('71.43'),
            cod_charge=Decimal('49.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('1549.00')
        )
        
        OrderItem.objects.create(
            order=order,
            product=self.prod_1500,
            quantity=1,
            price=Decimal('1500.00')
        )
        
        # Send owner notification
        success = send_owner_order_notification_email(order)
        self.assertTrue(success)
        
        # Check outbox
        # Because it's dispatched via threading, join threads or verify rendered template directly
        from django.template.loader import render_to_string
        from decimal import ROUND_HALF_UP
        
        total_gst = Decimal(str(order.tax_amount))
        cgst = (total_gst / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sgst = total_gst - cgst
        taxable_value = order.subtotal - order.discount_amount - total_gst
        
        rendered = render_to_string('shop/emails/admin_order_notification.html', {
            'order': order,
            'items': order.items.all(),
            'site_settings': self.settings,
            'gst_number': self.settings.gst_number,
            'currency': self.settings.currency,
            'taxable_value': taxable_value,
            'total_gst_amount': total_gst,
            'cgst_amount': cgst,
            'sgst_amount': sgst,
        })
        
        # Assert accounting details in email HTML
        self.assertIn("33AAAAA0000A1Z5", rendered) # GSTIN
        self.assertIn("5% (CGST 2.5% + SGST 2.5%)", rendered) # GST Rate
        self.assertIn("35.72", rendered) # CGST
        self.assertIn("35.71", rendered) # SGST
        self.assertIn("71.43", rendered) # Total GST
        self.assertIn("49.00", rendered) # COD charge applied
        self.assertIn("1549.00", rendered) # Grand total
        self.assertIn("SS-1500", rendered) # SKU
        self.assertIn("Soft Silk Saree 1500", rendered) # Product name

    def test_customer_facing_invoice_templates_no_separate_gst_line(self):
        """Verify order_success and order_detail do NOT display a separate GST line."""
        order = Order.objects.create(
            user=self.user,
            order_number="RS-INVOICE123",
            full_name="Abhi Vigu",
            phone_number="9876543210",
            email="customer@example.com",
            address_line_1="10 Main Silk Road",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=Decimal('1500.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('71.43'),
            cod_charge=Decimal('49.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('1549.00')
        )
        
        from django.template.loader import render_to_string
        
        # Test order_success.html
        html_success = render_to_string('shop/order_success.html', {
            'order': order,
            'site_settings': self.settings,
        })
        self.assertNotIn("GST/Tax:", html_success)
        self.assertNotIn("GST 5%", html_success)
        self.assertIn("(Inclusive of all taxes)", html_success)
        self.assertIn("33AAAAA0000A1Z5", html_success)
        self.assertIn("COD Charge:", html_success)
        self.assertIn('id="printable-invoice"', html_success)
        self.assertIn('@media print', html_success)
        self.assertIn('no-print', html_success)
        self.assertIn('TAX INVOICE', html_success)
        self.assertIn('invoice-print-footer', html_success)
        
        # Test order_detail.html
        html_detail = render_to_string('shop/order_detail.html', {
            'order': order,
            'site_settings': self.settings,
        })
        self.assertNotIn("GST/Tax:", html_detail)
        self.assertNotIn("GST 5%", html_detail)
        self.assertIn("(Inclusive of all taxes)", html_detail)
        self.assertIn("33AAAAA0000A1Z5", html_detail)
        self.assertIn("COD Charge:", html_detail)
        self.assertIn('id="printable-invoice"', html_detail)
        self.assertIn('@media print', html_detail)
        self.assertIn('order-tracking-card no-print', html_detail)
        self.assertIn('TAX INVOICE', html_detail)
        self.assertIn('invoice-print-footer', html_detail)

    def test_checkout_and_order_create_rejects_cod(self):
        """Verify COD is rejected on order_create and redirects to checkout."""
        client = Client()
        client.force_login(self.user)
        
        # Add product to cart
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.prod_2000, quantity=1)
        
        response = client.post(reverse('shop:order_create'), {
            'address_id': self.address.id,
            'payment_method': 'COD'
        })
        
        # Should redirect to checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('shop:checkout'), response.url)
        self.assertEqual(Order.objects.count(), 0)

    def test_admin_can_edit_invoice_from_backend(self):
        """Verify that an admin can edit customer name, billing GST number, and address from backend, while amounts remain locked."""
        admin_user = User.objects.create_superuser(
            username="testadmin",
            email="admin@rangamsaradhasilks.com",
            password="adminpassword123"
        )
        order = Order.objects.create(
            user=self.user,
            order_number="RS-EDIT-999",
            full_name="Original Customer Name",
            gst_number="",
            phone_number="9876543210",
            email="orig@example.com",
            address_line_1="10 Main St",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=Decimal('1500.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('71.43'),
            cod_charge=Decimal('49.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('1549.00')
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.prod_1500,
            quantity=1,
            price=Decimal('1500.00')
        )
        
        client = Client()
        client.force_login(admin_user)
        # SeparateSessionMiddleware expects admin_sessionid cookie for /admin/ requests
        client.cookies['admin_sessionid'] = client.cookies['sessionid'].value
        
        # 1. Access the custom admin change form
        admin_change_url = reverse('custom_admin:shop_order_change', args=[order.pk])
        resp = client.get(admin_change_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Customer Name")
        self.assertNotContains(resp, "Store GSTIN (Invoice Heading)")
        self.assertContains(resp, "Amounts Locked")
        
        # 2. Post updated billing details (Customer Name, Contact, Address, Status)
        # Note: financial amounts and GST are locked/managed at site settings level
        post_data = {
            'order_status': 'CONFIRMED',
            'payment_status': 'PAID',
            'payment_method': 'ONLINE',
            'full_name': 'Rangam Silk Traders Pvt Ltd',
            'phone_number': '9123456780',
            'email': 'billing@rangamsilktraders.com',
            'address_line_1': '45 Silk Palace Road',
            'address_line_2': 'Suite 200',
            'city': 'Kanchipuram',
            'state': 'Tamil Nadu',
            'pincode': '631501',
            'landmark': 'Near Temple',
            # Formset management
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': str(item.pk),
            '_save': 'Save Billing & Order Changes'
        }
        
        post_resp = client.post(admin_change_url, post_data, follow=True)
        self.assertEqual(post_resp.status_code, 200)
        
        # 3. Verify billing info was updated in DB
        order.refresh_from_db()
        self.assertEqual(order.full_name, 'Rangam Silk Traders Pvt Ltd')
        self.assertEqual(order.email, 'billing@rangamsilktraders.com')
        self.assertEqual(order.city, 'Kanchipuram')
        self.assertEqual(order.payment_method, 'ONLINE')
        self.assertEqual(order.order_status, 'CONFIRMED')
        self.assertEqual(order.payment_status, 'PAID')
        
        # 4. Verify financial amounts remained safely locked and unmanipulated
        self.assertEqual(order.subtotal, Decimal('1500.00'))
        self.assertEqual(order.tax_amount, Decimal('71.43'))
        self.assertEqual(order.grand_total, Decimal('1549.00'))
        
        # 5. Verify customer invoice displays the store GSTIN in heading, and NO duplicate under customer name
        client.force_login(self.user)
        invoice_url = reverse('shop:order_detail', args=[order.order_number])
        invoice_resp = client.get(invoice_url)
        self.assertEqual(invoice_resp.status_code, 200)
        self.assertContains(invoice_resp, 'Rangam Silk Traders Pvt Ltd')
        self.assertContains(invoice_resp, '33AAAAA0000A1Z5')
        self.assertNotContains(invoice_resp, 'GSTIN / GST No')

    def test_admin_can_set_tracking_link_and_customer_can_track(self):
        """Verify admin can add tracking link and number from admin panel and customer can track package."""
        admin_user = User.objects.create_superuser(
            username="shipadmin",
            email="shipping@rangamsaradhasilks.com",
            password="adminpassword123"
        )
        order = Order.objects.create(
            user=self.user,
            order_number="RS-TRACK-101",
            full_name="Abhi Vigu",
            phone_number="9876543210",
            email="customer@example.com",
            address_line_1="10 Main Silk Road",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=Decimal('1500.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('71.43'),
            cod_charge=Decimal('49.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('1549.00')
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.prod_1500,
            quantity=1,
            price=Decimal('1500.00')
        )

        client = Client()
        client.force_login(admin_user)
        client.cookies['admin_sessionid'] = client.cookies['sessionid'].value

        # 1. Access admin change form and verify tracking fields are present
        admin_change_url = reverse('custom_admin:shop_order_change', args=[order.pk])
        resp = client.get(admin_change_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Shipment & Tracking")
        self.assertContains(resp, "Courier Tracking Link / URL")
        self.assertContains(resp, "AWB / Tracking Number")

        # 2. Update tracking link, AWB number and mark as SHIPPED
        tracking_url = "https://www.delhivery.com/track/package/DEL987654321IN"
        tracking_num = "DEL987654321IN"
        post_data = {
            'order_status': 'SHIPPED',
            'payment_status': 'PAID',
            'payment_method': 'ONLINE',
            'tracking_link': tracking_url,
            'tracking_number': tracking_num,
            'full_name': 'Abhi Vigu',
            'phone_number': '9876543210',
            'email': 'customer@example.com',
            'address_line_1': '10 Main Silk Road',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            # Formset management
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': str(item.pk),
            '_save': 'Save Billing & Order Changes'
        }
        post_resp = client.post(admin_change_url, post_data, follow=True)
        self.assertEqual(post_resp.status_code, 200)

        # 3. Verify saved in DB
        order.refresh_from_db()
        self.assertEqual(order.tracking_link, tracking_url)
        self.assertEqual(order.tracking_number, tracking_num)
        self.assertEqual(order.order_status, 'SHIPPED')

        # 4. Verify admin form now displays the active test link
        resp_after_save = client.get(admin_change_url)
        self.assertContains(resp_after_save, "Active Link Configured")
        self.assertContains(resp_after_save, tracking_url)

        # 5. Customer checks order tracking on order_detail.html
        client.force_login(self.user)
        invoice_url = reverse('shop:order_detail', args=[order.order_number])
        detail_resp = client.get(invoice_url)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, tracking_url)
        self.assertContains(detail_resp, tracking_num)
        self.assertContains(detail_resp, "Track Package")
        self.assertContains(detail_resp, "Track Shipment")

        # 6. Check order_success.html also displays tracking button
        from django.template.loader import render_to_string
        html_success = render_to_string('shop/order_success.html', {
            'order': order,
            'site_settings': self.settings
        })
        self.assertIn(tracking_url, html_success)
        self.assertIn("Track Shipment", html_success)

    def test_cart_quantity_decrease_to_zero_clears_item(self):
        """When quantity is 1 and user decreases it to 0, item should be cleared from cart."""
        from shop.models import Cart, CartItem
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.prod_1500, quantity=1)

        client = Client()
        client.force_login(self.user)

        # Update cart quantity to 0
        update_url = reverse('shop:cart_update', args=[item.id])
        response = client.post(update_url, {'quantity': '0'}, follow=True)

        self.assertEqual(response.status_code, 200)
        # CartItem should be deleted
        self.assertFalse(CartItem.objects.filter(id=item.id).exists())
        self.assertEqual(cart.items.count(), 0)
        self.assertContains(response, "Item removed from Cart.")

