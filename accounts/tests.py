from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

User = get_user_model()

class GoogleAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.google_login_url = reverse('accounts:google_login')

    def test_google_login_missing_token(self):
        response = self.client.post(self.google_login_url, {}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('missing', data['message'])

    @patch('requests.get')
    def test_google_login_new_user_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'email': 'newgoogleuser@example.com',
            'email_verified': 'true',
            'sub': '12345678901234567890',
            'name': 'Google User',
            'given_name': 'Google',
            'family_name': 'User',
            'picture': 'https://lh3.googleusercontent.com/a/mockavatar'
        }
        mock_get.return_value = mock_response

        response = self.client.post(
            self.google_login_url,
            {'id_token': 'valid_mock_token'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        # Verify user in database
        user = User.objects.get(email='newgoogleuser@example.com')
        self.assertEqual(user.auth_provider, 'google')
        self.assertEqual(user.google_id, '12345678901234567890')
        self.assertEqual(user.profile_picture_url, 'https://lh3.googleusercontent.com/a/mockavatar')
        self.assertTrue(user.is_verified)

    @patch('requests.get')
    def test_google_login_existing_email_linking(self, mock_get):
        # Create existing user with email
        existing_user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='Password123!'
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'email': 'existing@example.com',
            'email_verified': 'true',
            'sub': '98765432109876543210',
            'name': 'Existing User',
            'given_name': 'Existing',
            'family_name': 'User',
            'picture': 'https://lh3.googleusercontent.com/a/mockavatar2'
        }
        mock_get.return_value = mock_response

        response = self.client.post(
            self.google_login_url,
            {'id_token': 'valid_mock_token_2'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        
        # Verify account linking
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.auth_provider, 'google')
        self.assertEqual(existing_user.google_id, '98765432109876543210')
        self.assertEqual(existing_user.profile_picture_url, 'https://lh3.googleusercontent.com/a/mockavatar2')
        self.assertTrue(existing_user.is_verified)


class FirebaseAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.firebase_login_url = reverse('accounts:firebase_login')

    def test_firebase_login_missing_token(self):
        response = self.client.post(self.firebase_login_url, {}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')

    @patch('firebase_admin.auth.verify_id_token')
    def test_firebase_login_new_user(self, mock_verify):
        mock_verify.return_value = {
            'uid': 'firebase_uid_123456',
            'email': 'firebaseuser@example.com',
            'name': 'Firebase Customer',
            'picture': 'https://lh3.googleusercontent.com/a/firebaseavatar'
        }

        response = self.client.post(
            self.firebase_login_url,
            {'id_token': 'mock_firebase_id_token'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        # Verify user in PostgreSQL
        user = User.objects.get(email='firebaseuser@example.com')
        self.assertEqual(user.firebase_uid, 'firebase_uid_123456')
        self.assertEqual(user.auth_provider, 'google')
        self.assertEqual(user.first_name, 'Firebase')
        self.assertEqual(user.last_name, 'Customer')
        self.assertEqual(user.profile_picture_url, 'https://lh3.googleusercontent.com/a/firebaseavatar')
        self.assertTrue(user.is_verified)


import datetime
from django.utils import timezone
from shop.models import Product, Category, CallBooking, Order

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
class CallBookingHistoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = 'TestPass123!'
        
        # Customer 1
        self.user1 = User.objects.create_user(
            username='customer1',
            email='customer1@example.com',
            first_name='Ananya',
            last_name='Rao',
            phone_number='9876543210',
            password=self.password
        )
        
        # Customer 2
        self.user2 = User.objects.create_user(
            username='customer2',
            email='customer2@example.com',
            first_name='Bhavana',
            last_name='Sharma',
            phone_number='9876543211',
            password=self.password
        )

        # Customer 3 (no bookings)
        self.user3 = User.objects.create_user(
            username='customer3',
            email='customer3@example.com',
            first_name='Chitra',
            last_name='Devi',
            phone_number='9876543212',
            password=self.password
        )

        # Product category & Products
        self.category = Category.objects.create(name='Silk Sarees', slug='silk-sarees')
        self.product1 = Product.objects.create(
            name='Kanchipuram Pure Silk Saree',
            slug='kanchipuram-pure-silk-saree',
            sku='KPS-101',
            price=12500.00,
            offer_price=9999.00,
            stock=5,
            is_active=True
        )
        self.product1.categories.add(self.category)

        self.product2 = Product.objects.create(
            name='Banarasi Brocade Saree',
            slug='banarasi-brocade-saree',
            sku='BBS-202',
            price=15000.00,
            offer_price=12000.00,
            stock=3,
            is_active=True
        )
        self.product2.categories.add(self.category)

        today = timezone.now().date()
        self.booking_date_1 = today + datetime.timedelta(days=2)
        self.booking_date_2 = today + datetime.timedelta(days=3)

        # Booking 1: belongs to user1
        self.booking1 = CallBooking.objects.create(
            booking_reference='BK-USER1-01',
            product=self.product1,
            user=self.user1,
            full_name='Ananya Rao',
            email='customer1@example.com',
            phone_number='9876543210',
            booking_date=self.booking_date_1,
            time_slot='10:00 AM - 11:00 AM',
            notes='Looking for wedding wear silk saree with heavy zari border.',
            status='CONFIRMED'
        )

        # Booking 2: belongs to user2
        self.booking2 = CallBooking.objects.create(
            booking_reference='BK-USER2-02',
            product=self.product2,
            user=self.user2,
            full_name='Bhavana Sharma',
            email='customer2@example.com',
            phone_number='9876543211',
            booking_date=self.booking_date_2,
            time_slot='02:00 PM - 03:00 PM',
            notes='Need color options shown on call.',
            status='PENDING'
        )

        # Booking 3: created with user1 email prior to login (user is null)
        self.booking3 = CallBooking.objects.create(
            booking_reference='BK-GUEST-03',
            product=self.product2,
            user=None,
            full_name='Ananya Rao',
            email='customer1@example.com',
            phone_number='9876543210',
            booking_date=self.booking_date_2,
            time_slot='04:00 PM - 05:00 PM',
            notes='Checking festival offers.',
            status='PENDING'
        )

    def test_logged_in_customer_can_see_own_call_bookings(self):
        """
        Verify that a logged-in customer sees all call bookings made with their account or email.
        """
        self.client.login(username='customer1', password=self.password)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

        # Check that user1's bookings appear in context and rendered HTML
        call_bookings = response.context['call_bookings']
        booking_refs = [b.booking_reference for b in call_bookings]
        self.assertIn('BK-USER1-01', booking_refs)
        self.assertIn('BK-GUEST-03', booking_refs)
        self.assertNotIn('BK-USER2-02', booking_refs)

        # Check rendered HTML
        content = response.content.decode('utf-8')
        self.assertIn('BK-USER1-01', content)
        self.assertIn('Kanchipuram Pure Silk Saree', content)
        self.assertIn('KPS-101', content)
        self.assertIn('Confirmed', content)

    def test_customer_cannot_see_other_customer_bookings(self):
        """
        Verify that a customer cannot see bookings belonging to other customers.
        """
        self.client.login(username='customer2', password=self.password)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

        call_bookings = response.context['call_bookings']
        booking_refs = [b.booking_reference for b in call_bookings]
        self.assertIn('BK-USER2-02', booking_refs)
        self.assertNotIn('BK-USER1-01', booking_refs)
        self.assertNotIn('BK-GUEST-03', booking_refs)

    def test_empty_booking_history_displays_correct_message_and_button(self):
        """
        Verify that when a user has no call bookings, the friendly empty state
        and 'Book a Call' action button are displayed.
        """
        self.client.login(username='customer3', password=self.password)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn("You haven't booked any calls yet.", content)
        self.assertIn("Book a Call", content)

    def test_customer_can_view_own_booking_detail(self):
        """
        Verify that an authenticated user can view the complete details of their own booking.
        """
        self.client.login(username='customer1', password=self.password)
        detail_url = reverse('accounts:booking_detail', args=['BK-USER1-01'])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('BK-USER1-01', content)
        self.assertIn('Kanchipuram Pure Silk Saree', content)
        self.assertIn('KPS-101', content)
        self.assertIn('Ananya Rao', content)
        self.assertIn('9876543210', content)
        self.assertIn('customer1@example.com', content)
        self.assertIn('10:00 AM - 11:00 AM', content)
        self.assertIn('Looking for wedding wear silk saree with heavy zari border.', content)
        self.assertIn('Confirmed', content)

    def test_customer_cannot_view_other_customer_booking_detail_returns_404(self):
        """
        Security verification: Attempting to access another customer's booking detail
        by manually altering the booking ID in the URL returns 404 (Not Found / Access Denied).
        """
        self.client.login(username='customer1', password=self.password)
        # Attempt to access customer2's booking
        other_user_booking_url = reverse('accounts:booking_detail', args=['BK-USER2-02'])
        response = self.client.get(other_user_booking_url)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_redirected_from_booking_detail(self):
        """
        Verify unauthenticated users cannot access booking detail and are redirected to login.
        """
        detail_url = reverse('accounts:booking_detail', args=['BK-USER1-01'])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_my_orders_and_call_bookings_remain_separate(self):
        """
        Verify that My Orders and My Call Bookings remain separate sections.
        """
        # Create an order for user1
        order = Order.objects.create(
            order_number="ORD-USER1-999",
            user=self.user1,
            full_name="Ananya Rao",
            phone_number="9876543210",
            email="customer1@example.com",
            address_line_1="123 Silk Lane",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            subtotal=9999.00,
            grand_total=9999.00
        )

        self.client.login(username='customer1', password=self.password)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

        # Context contains both separately
        self.assertIn(order, response.context['orders'])
        self.assertEqual(len(response.context['orders']), 1)
        self.assertEqual(len(response.context['call_bookings']), 2)

        # HTML contains both sections
        content = response.content.decode('utf-8')
        self.assertIn('ORD-USER1-999', content)
        self.assertIn('BK-USER1-01', content)


class BuyNowAuthRedirectFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "SecretPass123!"
        self.user = User.objects.create_user(
            username="buynow_user",
            email="buynow@example.com",
            phone_number="9876543210",
            password=self.password,
            is_active=True,
            is_verified=True
        )

        self.category = Category.objects.create(
            name="Semi Kanchipattu",
            slug="semi-kanchipattu"
        )
        self.product = Product.objects.create(
            name="Semi Kanchipattu Saree 01",
            slug="semi-kanchipattu-saree-01",
            price=5999.00,
            offer_price=4999.00,
            stock=10,
            is_active=True
        )
        self.product.categories.add(self.category)

    def test_case_1_logged_in_user_product_buy_now(self):
        """
        CASE 1: Logged-in user -> Product -> Buy Now
        Expected: existing Buy Now flow works normally (redirects directly to checkout).
        """
        self.client.login(username="buynow_user", password=self.password)
        cart_add_url = reverse('shop:cart_add', args=[self.product.id])
        
        response = self.client.post(cart_add_url, {'quantity': 1, 'buy_now': 'true'})
        # Should redirect directly to checkout
        self.assertRedirects(response, reverse('shop:checkout'))

    def test_case_2_logged_out_user_product_buy_now_and_login(self):
        """
        CASE 2: Logged-out user -> Product -> Buy Now -> Login
        Expected: after successful login, return to that exact Buy Now destination (checkout),
        preserving the selected product.
        """
        cart_add_url = reverse('shop:cart_add', args=[self.product.id])
        
        # 1. Logged-out user clicks Buy Now
        response = self.client.post(cart_add_url, {'quantity': 1, 'buy_now': 'true'})
        checkout_url = reverse('shop:checkout')
        login_url = reverse('accounts:login')
        expected_redirect_url = f"{login_url}?next={checkout_url}"
        
        self.assertRedirects(response, expected_redirect_url)

        # 2. View login page (GET): should retain next in form and context
        login_get = self.client.get(expected_redirect_url)
        self.assertEqual(login_get.status_code, 200)
        self.assertContains(login_get, f'value="{checkout_url}"')

        # 3. Submit credentials via POST with next parameter
        login_post = self.client.post(login_url, {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
            'next': checkout_url,
        })
        
        # Should redirect to checkout (NOT home:index)
        self.assertRedirects(login_post, checkout_url)

    def test_case_3_logged_out_user_category_product_buy_now_and_login(self):
        """
        CASE 3: Logged-out user -> Category -> Product -> Buy Now -> Login
        Expected: after login, continue with the selected product, NOT homepage.
        """
        # 1. Visit category page
        category_url = reverse('shop:category_detail', args=[self.category.slug])
        cat_resp = self.client.get(category_url)
        self.assertEqual(cat_resp.status_code, 200)

        # 2. Visit product detail page
        product_url = reverse('shop:product_detail', args=[self.product.slug])
        prod_resp = self.client.get(product_url)
        self.assertEqual(prod_resp.status_code, 200)

        # 3. Click Buy Now
        cart_add_url = reverse('shop:cart_add', args=[self.product.id])
        response = self.client.post(cart_add_url, {'quantity': 1, 'buy_now': 'true'}, HTTP_REFERER=product_url)
        checkout_url = reverse('shop:checkout')
        
        # 4. User is redirected to login with next
        self.assertIn(f"next={checkout_url}", response.url)

        # 5. User logs in
        login_url = reverse('accounts:login')
        login_post = self.client.post(f"{login_url}?next={checkout_url}", {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
            'next': checkout_url,
        })

        # Must redirect to checkout with selected product, NOT homepage
        self.assertRedirects(login_post, checkout_url)

    def test_case_4_shared_url_buy_now_flow(self):
        """
        CASE 4: User opens category page from a shared URL, selects any product, clicks Buy Now, logs in.
        Expected: return to the selected product's Buy Now flow.
        """
        shared_cat_url = f"/shop/category/{self.category.slug}/"
        resp = self.client.get(shared_cat_url)
        self.assertEqual(resp.status_code, 200)

        cart_add_url = reverse('shop:cart_add', args=[self.product.id])
        buy_now_resp = self.client.post(cart_add_url, {'quantity': 1, 'buy_now': 'true'})
        checkout_url = reverse('shop:checkout')
        
        self.assertIn(f"next={checkout_url}", buy_now_resp.url)

        # Login
        login_url = reverse('accounts:login')
        login_post = self.client.post(login_url, {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
            'next': checkout_url,
        })
        self.assertRedirects(login_post, checkout_url)

    def test_case_5_login_without_next_parameter(self):
        """
        CASE 5: Login without a next parameter.
        Expected: use the existing default redirect ('home:index').
        """
        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
        })
        self.assertRedirects(response, reverse('home:index'))

    def test_login_with_direct_product_next_parameter(self):
        """
        Direct next parameter pointing to product URL preserves and redirects to that exact product.
        """
        product_url = reverse('shop:product_detail', args=[self.product.slug])
        login_url = reverse('accounts:login')
        response = self.client.post(f"{login_url}?next={product_url}", {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
            'next': product_url,
        })
        self.assertRedirects(response, product_url)

    def test_open_redirect_vulnerability_prevention(self):
        """
        External and malicious URLs in next parameter are rejected and safely fallback to home:index.
        """
        malicious_urls = [
            'https://evil.com/phishing',
            '//evil.com/phishing',
            'http://attacker.com',
            'javascript:alert(1)',
        ]
        login_url = reverse('accounts:login')
        for bad_url in malicious_urls:
            response = self.client.post(f"{login_url}?next={bad_url}", {
                'login_type': 'password',
                'username': 'buynow_user',
                'password': self.password,
                'next': bad_url,
            })
            self.assertRedirects(response, reverse('home:index'))

    def test_admin_redirect_blocked_for_customer(self):
        """
        Customer logging in cannot be redirected to /admin paths; should fallback to home:index.
        """
        login_url = reverse('accounts:login')
        response = self.client.post(f"{login_url}?next=/admin/shop/order/", {
            'login_type': 'password',
            'username': 'buynow_user',
            'password': self.password,
            'next': '/admin/shop/order/',
        })
        self.assertRedirects(response, reverse('home:index'))

    def test_already_authenticated_user_with_next_redirects_to_destination(self):
        """
        Requirement 2: Do NOT redirect authenticated users to the homepage after login when a valid next destination exists.
        """
        self.client.login(username="buynow_user", password=self.password)
        product_url = reverse('shop:product_detail', args=[self.product.slug])
        login_url = reverse('accounts:login')
        response = self.client.get(f"{login_url}?next={product_url}")
        self.assertRedirects(response, product_url)

    def test_already_authenticated_user_without_next_redirects_to_home(self):
        """
        Requirement 3: If there is no next destination, keep the existing default login redirect behavior.
        """
        self.client.login(username="buynow_user", password=self.password)
        login_url = reverse('accounts:login')
        response = self.client.get(login_url)
        self.assertRedirects(response, reverse('home:index'))

    @patch('requests.get')
    def test_google_login_with_buy_now_merges_cart_and_redirects_to_checkout(self, mock_get):
        """
        Verify that when a guest user clicks Buy Now and logs in via Google,
        their guest cart items are merged into their user account and they are redirected to checkout,
        where the cart is NOT empty (does not redirect to /shop/cart/).
        """
        from shop.models import Cart, CartItem
        # 1. Guest clicks Buy Now
        cart_add_url = reverse('shop:cart_add', args=[self.product.id])
        response = self.client.post(cart_add_url, {'quantity': 2, 'buy_now': 'true'})
        checkout_url = reverse('shop:checkout')
        self.assertIn(f"next={checkout_url}", response.url)

        # 2. Mock Google auth
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'email': 'buynow@example.com',
            'email_verified': 'true',
            'sub': '987654321_google_sub',
            'name': 'Buy Now User',
            'picture': 'https://lh3.googleusercontent.com/mock.jpg'
        }
        mock_get.return_value = mock_response

        # 3. Perform Google login via AJAX POST with next parameter
        google_login_url = reverse('accounts:google_login')
        login_resp = self.client.post(
            google_login_url,
            {'id_token': 'mock_token', 'next': checkout_url},
            content_type='application/json'
        )
        self.assertEqual(login_resp.status_code, 200)
        data = login_resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['redirect_url'], checkout_url)

        # 4. User's cart should now contain the product
        user_cart = Cart.objects.get(user=self.user)
        self.assertTrue(user_cart.items.filter(product=self.product).exists())
        self.assertEqual(user_cart.items.get(product=self.product).quantity, 2)

        # 5. Access checkout: should succeed (200 OK), NOT redirect to /shop/cart/
        checkout_resp = self.client.get(checkout_url)
        self.assertEqual(checkout_resp.status_code, 200)
        self.assertContains(checkout_resp, "Semi Kanchipattu Saree 01")





