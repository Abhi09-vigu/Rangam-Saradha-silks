import hmac
import hashlib
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from shop.models import Category, Product, Cart, CartItem, Order, OrderItem
from accounts.models import Address
from home.models import WebsiteSetting
from shop.razorpay_service import verify_payment_signature

User = get_user_model()


class RazorpayIntegrationTests(TestCase):
    def setUp(self):
        # Configure test settings
        self.settings_obj = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silks",
            tax_percentage=5.00,
            shipping_charge=50.00,
            free_shipping_limit=1000.00,
            currency="₹"
        )

        # Create customer user
        self.user = User.objects.create_user(
            username="lakshmi_priya",
            email="customer@example.com",
            phone_number="+919876543210",
            first_name="Lakshmi",
            last_name="Priya",
            password="SecurePassword123!"
        )

        # Create address
        self.address = Address.objects.create(
            user=self.user,
            full_name="Lakshmi Priya",
            phone_number="9876543210",
            address_line_1="108 Temple Street",
            city="Kanchipuram",
            state="Tamil Nadu",
            pincode="631501",
            address_type="Home",
            is_default=True
        )

        # Create category and product
        self.category = Category.objects.create(name="Kanchipuram Silks", slug="kanchipuram-silks")
        self.product = Product.objects.create(
            name="Crimson Pure Zari Silk Saree",
            slug="crimson-pure-zari-silk-saree",
            sku="RSS-CRM-001",
            price=Decimal("1200.00"),
            stock=5,
            is_active=True
        )
        self.product.categories.add(self.category)

        self.client = Client()
        self.client.force_login(self.user)

        # Add product to user's cart
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    @patch("shop.views.create_razorpay_order")
    def test_razorpay_create_order_authoritative_calculation(self, mock_create_rzp_order):
        """
        Verify Razorpay order creation authoritatively calculates amount on the backend:
        Product: 1200.00 + 5% GST = 1260.00. Free shipping (>=1000). Total: 1260.00.
        Amount in paise: 126000.
        Stock is NOT deducted and Cart is NOT cleared.
        """
        mock_create_rzp_order.return_value = {
            'id': 'order_rzp_test_12345',
            'amount': 126000,
            'currency': 'INR',
            'status': 'created'
        }

        url = reverse('shop:razorpay_create_order')
        response = self.client.post(
            url,
            data={'address_id': self.address.id},
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['razorpay_order_id'], 'order_rzp_test_12345')
        self.assertEqual(data['amount'], 126000)

        # Verify Pending Order created in DB
        order = Order.objects.get(razorpay_order_id='order_rzp_test_12345')
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.payment_method, 'RAZORPAY')
        self.assertEqual(order.payment_status, 'PENDING')
        self.assertEqual(order.order_status, 'PENDING')
        self.assertEqual(order.grand_total, Decimal('1260.00'))

        # Verify stock was NOT deducted prematurely
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # Verify cart items were NOT deleted
        self.assertTrue(self.cart.items.exists())

    def test_razorpay_create_order_insufficient_stock(self):
        """Verify order creation fails if product stock is lower than cart quantity."""
        self.product.stock = 0
        self.product.save()

        url = reverse('shop:razorpay_create_order')
        response = self.client.post(
            url,
            data={'address_id': self.address.id},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn("insufficient stock", data['error'].lower())

    @patch("shop.views.verify_payment_signature")
    def test_razorpay_verify_payment_success(self, mock_verify_signature):
        """
        Verify successful payment verification:
        1. Validates signature.
        2. Sets payment_status = PAID, order_status = CONFIRMED.
        3. Saves razorpay_payment_id and razorpay_signature.
        4. Decrements product stock exactly once.
        5. Clears customer cart.
        """
        mock_verify_signature.return_value = True

        # Pre-create pending order
        order = Order.objects.create(
            user=self.user,
            order_number="RS-TEST0001",
            full_name=self.address.full_name,
            phone_number=self.address.phone_number,
            email=self.user.email,
            address_line_1=self.address.address_line_1,
            city=self.address.city,
            state=self.address.state,
            pincode=self.address.pincode,
            payment_method='RAZORPAY',
            payment_status='PENDING',
            order_status='PENDING',
            subtotal=Decimal('1260.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('60.00'),
            cod_charge=Decimal('0.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('1260.00'),
            razorpay_order_id='order_rzp_test_12345'
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            price=Decimal('1260.00')
        )

        url = reverse('shop:razorpay_verify_payment')
        payload = {
            'razorpay_order_id': 'order_rzp_test_12345',
            'razorpay_payment_id': 'pay_rzp_test_98765',
            'razorpay_signature': 'mock_valid_signature_abc123'
        }
        response = self.client.post(url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'PAID')
        self.assertEqual(order.order_status, 'CONFIRMED')
        self.assertEqual(order.razorpay_payment_id, 'pay_rzp_test_98765')
        self.assertEqual(order.razorpay_signature, 'mock_valid_signature_abc123')
        self.assertIsNotNone(order.paid_at)

        # Inventory decremented by 1 (5 -> 4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

        # Cart cleared
        self.assertFalse(self.cart.items.exists())

    @patch("shop.views.verify_payment_signature")
    def test_razorpay_verify_payment_idempotency(self, mock_verify_signature):
        """
        Duplicate calls to verify-payment must NOT decrement inventory twice.
        """
        mock_verify_signature.return_value = True

        order = Order.objects.create(
            user=self.user,
            order_number="RS-TEST0002",
            full_name=self.address.full_name,
            phone_number=self.address.phone_number,
            email=self.user.email,
            address_line_1=self.address.address_line_1,
            city=self.address.city,
            state=self.address.state,
            pincode=self.address.pincode,
            payment_method='RAZORPAY',
            payment_status='PAID',  # Already paid
            order_status='CONFIRMED',
            subtotal=Decimal('1260.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('60.00'),
            grand_total=Decimal('1260.00'),
            razorpay_order_id='order_rzp_duplicate_check',
            razorpay_payment_id='pay_duplicate_123'
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            price=Decimal('1260.00')
        )

        initial_stock = self.product.stock

        url = reverse('shop:razorpay_verify_payment')
        payload = {
            'razorpay_order_id': 'order_rzp_duplicate_check',
            'razorpay_payment_id': 'pay_duplicate_123',
            'razorpay_signature': 'mock_signature'
        }
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Stock remains unchanged
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock)

    @patch("shop.views.verify_payment_signature")
    def test_razorpay_verify_payment_invalid_signature(self, mock_verify_signature):
        """
        Invalid signature must be rejected:
        - Return 400 error.
        - Mark order as FAILED.
        - Do NOT deduct stock.
        - Do NOT delete cart items.
        """
        mock_verify_signature.return_value = False

        order = Order.objects.create(
            user=self.user,
            order_number="RS-TEST0003",
            full_name=self.address.full_name,
            phone_number=self.address.phone_number,
            email=self.user.email,
            address_line_1=self.address.address_line_1,
            city=self.address.city,
            state=self.address.state,
            pincode=self.address.pincode,
            payment_method='RAZORPAY',
            payment_status='PENDING',
            order_status='PENDING',
            subtotal=Decimal('1260.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('60.00'),
            grand_total=Decimal('1260.00'),
            razorpay_order_id='order_rzp_tampered'
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            price=Decimal('1260.00')
        )

        url = reverse('shop:razorpay_verify_payment')
        payload = {
            'razorpay_order_id': 'order_rzp_tampered',
            'razorpay_payment_id': 'pay_fake',
            'razorpay_signature': 'tampered_signature'
        }
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'FAILED')

        # Stock safe
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # Cart safe
        self.assertTrue(self.cart.items.exists())

    def test_razorpay_payment_failed_view(self):
        """
        When customer dismisses or cancels the modal:
        - Marks order as FAILED.
        - Stock is NOT deducted.
        - Cart is NOT deleted.
        """
        order = Order.objects.create(
            user=self.user,
            order_number="RS-TEST0004",
            full_name=self.address.full_name,
            phone_number=self.address.phone_number,
            email=self.user.email,
            address_line_1=self.address.address_line_1,
            city=self.address.city,
            state=self.address.state,
            pincode=self.address.pincode,
            payment_method='RAZORPAY',
            payment_status='PENDING',
            order_status='PENDING',
            subtotal=Decimal('1260.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('60.00'),
            grand_total=Decimal('1260.00'),
            razorpay_order_id='order_rzp_dismissed'
        )

        url = reverse('shop:razorpay_payment_failed')
        response = self.client.post(
            url,
            data={'razorpay_order_id': 'order_rzp_dismissed', 'reason': 'Customer closed popup'},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'FAILED')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertTrue(self.cart.items.exists())

    def test_cod_flow_is_rejected(self):
        """
        Cash on Delivery is discontinued. Any attempt to submit COD via order_create
        is safely rejected with an error message and redirects to checkout.
        """
        initial_stock = self.product.stock
        url = reverse('shop:order_create')
        response = self.client.post(url, data={
            'address_id': self.address.id,
            'payment_method': 'COD'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('shop:checkout'), response.url)

        # Check no COD order was created
        cod_order = Order.objects.filter(user=self.user, payment_method='COD').first()
        self.assertIsNone(cod_order)

        # Stock intact
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock)

        # Cart still exists
        self.assertTrue(self.cart.items.exists())

    def test_service_signature_verification_hmac(self):
        """
        Test that shop.razorpay_service.verify_payment_signature correctly validates
        genuine signatures and rejects modified signatures using HMAC-SHA256.
        """
        secret = "test_razorpay_secret_key_999"
        order_id = "order_12345"
        payment_id = "pay_67890"

        # Generate genuine HMAC SHA256 signature
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_signature = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        with patch.object(settings, 'RAZORPAY_KEY_SECRET', secret):
            # Test valid signature
            self.assertTrue(verify_payment_signature(order_id, payment_id, valid_signature))
            # Test tampered signature
            self.assertFalse(verify_payment_signature(order_id, payment_id, "tampered_signature_123"))
            # Test wrong order id
            self.assertFalse(verify_payment_signature("order_wrong", payment_id, valid_signature))
