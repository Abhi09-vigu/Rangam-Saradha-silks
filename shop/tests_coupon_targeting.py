from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from shop.models import Category, Product, Coupon, Cart, CartItem
from django.contrib.auth import get_user_model
User = get_user_model()

class CouponTargetingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')
        
        # Categories
        self.cat_silk = Category.objects.create(name='Silk Sarees', slug='silk-sarees')
        self.cat_cotton = Category.objects.create(name='Cotton Sarees', slug='cotton-sarees')
        
        # Products
        self.prod_kanchi = Product.objects.create(
            name='Kanchipuram Silk Saree',
            slug='kanchipuram-silk-saree',
            sku='SKU-KANCHI-01',
            price=Decimal('5000.00'),
            stock=10,
            is_active=True
        )
        self.prod_kanchi.categories.add(self.cat_silk)

        self.prod_banarasi = Product.objects.create(
            name='Banarasi Silk Saree',
            slug='banarasi-silk-saree',
            sku='SKU-BANARASI-01',
            price=Decimal('4000.00'),
            stock=10,
            is_active=True
        )
        self.prod_banarasi.categories.add(self.cat_silk)

        self.prod_cotton = Product.objects.create(
            name='Chanderi Cotton Saree',
            slug='chanderi-cotton-saree',
            sku='SKU-COTTON-01',
            price=Decimal('2000.00'),
            stock=10,
            is_active=True
        )
        self.prod_cotton.categories.add(self.cat_cotton)
        
        # Cart for user
        self.cart = Cart.objects.create(user=self.user)
        # Cart has 1 Kanchipuram (5000) and 1 Cotton (2000) -> total 7000
        CartItem.objects.create(cart=self.cart, product=self.prod_kanchi, quantity=1)
        CartItem.objects.create(cart=self.cart, product=self.prod_cotton, quantity=1)

    @property
    def cart_total(self):
        return sum(item.get_total_price() for item in self.cart.items.all())

    def test_all_products_coupon(self):
        """Coupon applicable to all products applies discount to total cart"""
        coupon = Coupon.objects.create(
            code='ALL10',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        self.assertTrue(coupon.is_valid(self.cart_total, cart=self.cart))
        
        discount = coupon.calculate_discount(self.cart_total, cart=self.cart)
        # 10% of 7000 = 700
        self.assertEqual(discount, Decimal('700.00'))

    def test_category_coupon_eligible_and_ineligible(self):
        """Category-specific coupon applies discount ONLY to items in that category"""
        coupon = Coupon.objects.create(
            code='SILK20',
            discount_type='PERCENT',
            discount_value=Decimal('20.00'),
            apply_to='CATEGORIES',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        coupon.categories.add(self.cat_silk)
        
        self.assertTrue(coupon.is_valid(self.cart_total, cart=self.cart))
        
        # Eligible item is Kanchipuram Silk (5000). Cotton (2000) is not eligible.
        # 20% of 5000 = 1000
        discount = coupon.calculate_discount(self.cart_total, cart=self.cart)
        self.assertEqual(discount, Decimal('1000.00'))

    def test_category_coupon_no_eligible_items(self):
        """Category-specific coupon fails validation if cart has no items in category"""
        coupon = Coupon.objects.create(
            code='BRIDAL50',
            discount_type='PERCENT',
            discount_value=Decimal('50.00'),
            apply_to='CATEGORIES',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        cat_bridal = Category.objects.create(name='Bridal Sarees', slug='bridal-sarees')
        coupon.categories.add(cat_bridal)
        
        self.assertFalse(coupon.is_valid(self.cart_total, cart=self.cart))

    def test_product_coupon_eligible_and_ineligible(self):
        """Product-specific coupon applies discount ONLY to targeted products"""
        coupon = Coupon.objects.create(
            code='KANCHI500',
            discount_type='FIXED',
            discount_value=Decimal('500.00'),
            apply_to='PRODUCTS',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        coupon.products.add(self.prod_kanchi)
        
        self.assertTrue(coupon.is_valid(self.cart_total, cart=self.cart))
        
        discount = coupon.calculate_discount(self.cart_total, cart=self.cart)
        # Fixed 500 on eligible 5000 item
        self.assertEqual(discount, Decimal('500.00'))

    def test_product_coupon_not_in_cart(self):
        """Product-specific coupon fails validation if product is not in cart"""
        coupon = Coupon.objects.create(
            code='BANARASI10',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='PRODUCTS',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        coupon.products.add(self.prod_banarasi)
        
        self.assertFalse(coupon.is_valid(self.cart_total, cart=self.cart))

    def test_start_date_in_future(self):
        """Coupon with future start date is not yet active"""
        coupon = Coupon.objects.create(
            code='FUTURE10',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            start_date=timezone.now() + timedelta(days=2),
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        self.assertFalse(coupon.is_valid(self.cart_total, cart=self.cart))

    def test_start_time_today(self):
        """Coupon starting later today is not yet active; coupon starting earlier today is active"""
        now = timezone.localtime() if timezone.is_aware(timezone.now()) else datetime.datetime.now()
        # Future time today
        future_time = (now + timedelta(hours=2)).time()
        coupon_future = Coupon.objects.create(
            code='TODAYLATER',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            start_date=now.date(),
            start_time=future_time,
            expiry_date=now.date() + timedelta(days=5),
            is_active=True
        )
        self.assertFalse(coupon_future.is_valid(self.cart_total, cart=self.cart))

        # Past time today
        past_time = (now - timedelta(hours=2)).time()
        coupon_past = Coupon.objects.create(
            code='TODAYEARLIER',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            start_date=now.date(),
            start_time=past_time,
            expiry_date=now.date() + timedelta(days=5),
            is_active=True
        )
        self.assertTrue(coupon_past.is_valid(self.cart_total, cart=self.cart))

    def test_expiry_time_today(self):
        """Coupon expiring earlier today is expired; coupon expiring later today is active"""
        now = timezone.localtime() if timezone.is_aware(timezone.now()) else datetime.datetime.now()
        past_time = (now - timedelta(hours=2)).time()
        coupon_expired = Coupon.objects.create(
            code='EXPIREDTODAY',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            start_date=now.date() - timedelta(days=1),
            expiry_date=now.date(),
            expiry_time=past_time,
            is_active=True
        )
        self.assertFalse(coupon_expired.is_valid(self.cart_total, cart=self.cart))

        future_time = (now + timedelta(hours=2)).time()
        coupon_active = Coupon.objects.create(
            code='ACTIVETODAY',
            discount_type='PERCENT',
            discount_value=Decimal('10.00'),
            apply_to='ALL',
            start_date=now.date() - timedelta(days=1),
            expiry_date=now.date(),
            expiry_time=future_time,
            is_active=True
        )
        self.assertTrue(coupon_active.is_valid(self.cart_total, cart=self.cart))

    def test_fixed_discount_capped_at_eligible_total(self):
        """Fixed discount cannot exceed eligible items total"""
        coupon = Coupon.objects.create(
            code='BIGCOTTON',
            discount_type='FIXED',
            discount_value=Decimal('3000.00'),
            apply_to='CATEGORIES',
            expiry_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        coupon.categories.add(self.cat_cotton) # Cotton is only 2000 in cart
        
        discount = coupon.calculate_discount(self.cart_total, cart=self.cart)
        # Should be capped at cotton subtotal (2000), not full 3000
        self.assertEqual(discount, Decimal('2000.00'))
