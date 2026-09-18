from django.test import TestCase, Client
from django.utils import timezone
from unittest.mock import patch
import datetime
from shop.models import Product, Category, CallBooking, CallSlot
from shop.views import parse_slot_start_time, get_slots_status_for_date
from accounts.models import CustomUser


class SlotTimeAndBookingFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Kanchipuram Silk", slug="kanchipuram-silk", is_active=True)
        self.product = Product.objects.create(
            name="Pure Kanchipuram Silk Saree",
            slug="pure-kanchipuram-silk-saree",
            sku="SKU12345",
            price=15000.00,
            stock=10,
            is_active=True
        )
        self.user = CustomUser.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="password123",
            phone_number="9876543210"
        )

    def test_parse_slot_start_time(self):
        self.assertEqual(parse_slot_start_time("10:00 AM - 11:00 AM"), datetime.time(10, 0))
        self.assertEqual(parse_slot_start_time("11:00 AM - 12:00 PM"), datetime.time(11, 0))
        self.assertEqual(parse_slot_start_time("02:00 PM - 03:00 PM"), datetime.time(14, 0))
        self.assertEqual(parse_slot_start_time("04:00 PM - 05:00 PM"), datetime.time(16, 0))
        self.assertEqual(parse_slot_start_time("06:00 PM - 07:00 PM"), datetime.time(18, 0))
        self.assertIsNone(parse_slot_start_time("Invalid Slot"))
        self.assertIsNone(parse_slot_start_time(""))

    def test_slots_crossed_time_marked_not_selectable(self):
        """
        At 2:17 PM (14:17), slots for 10:00 AM, 11:00 AM, and 02:00 PM have crossed
        and must be marked TIME_PASSED and is_selectable=False.
        04:00 PM and 06:00 PM must remain AVAILABLE and is_selectable=True.
        """
        test_now = timezone.make_aware(datetime.datetime(2026, 9, 18, 14, 17, 0))
        with patch('django.utils.timezone.localtime', return_value=test_now):
            slots = get_slots_status_for_date(test_now.date())
            slot_map = {s['time_slot']: s for s in slots}

            self.assertFalse(slot_map['10:00 AM - 11:00 AM']['is_selectable'])
            self.assertEqual(slot_map['10:00 AM - 11:00 AM']['status'], 'TIME_PASSED')

            self.assertFalse(slot_map['11:00 AM - 12:00 PM']['is_selectable'])
            self.assertEqual(slot_map['11:00 AM - 12:00 PM']['status'], 'TIME_PASSED')

            self.assertFalse(slot_map['02:00 PM - 03:00 PM']['is_selectable'])
            self.assertEqual(slot_map['02:00 PM - 03:00 PM']['status'], 'TIME_PASSED')

            self.assertTrue(slot_map['04:00 PM - 05:00 PM']['is_selectable'])
            self.assertEqual(slot_map['04:00 PM - 05:00 PM']['status'], 'AVAILABLE')

            self.assertTrue(slot_map['06:00 PM - 07:00 PM']['is_selectable'])
            self.assertEqual(slot_map['06:00 PM - 07:00 PM']['status'], 'AVAILABLE')

    def test_booked_slot_marked_not_selectable_and_callslot_updated(self):
        """
        When a slot is booked, it is marked BOOKED and is_selectable=False.
        """
        test_now = timezone.make_aware(datetime.datetime(2026, 9, 18, 9, 0, 0))
        with patch('django.utils.timezone.localtime', return_value=test_now):
            CallBooking.objects.create(
                product=self.product,
                user=self.user,
                full_name="Abhi",
                phone_number="9876543210",
                booking_date=test_now.date(),
                time_slot="04:00 PM - 05:00 PM",
                status="CONFIRMED"
            )
            slots = get_slots_status_for_date(test_now.date())
            slot_map = {s['time_slot']: s for s in slots}

            self.assertFalse(slot_map['04:00 PM - 05:00 PM']['is_selectable'])
            self.assertEqual(slot_map['04:00 PM - 05:00 PM']['status'], 'BOOKED')
            self.assertTrue(slot_map['06:00 PM - 07:00 PM']['is_selectable'])

    def test_post_booking_rejection_for_passed_slot(self):
        """
        Submitting a booking for a slot whose time has crossed must be rejected.
        """
        self.client.force_login(self.user)
        test_now = timezone.make_aware(datetime.datetime(2026, 9, 18, 14, 17, 0))
        with patch('django.utils.timezone.localtime', return_value=test_now):
            response = self.client.post(f"/shop/product/{self.product.slug}/book-call/", {
                'full_name': 'Test User',
                'phone_number': '9876543210',
                'booking_date': '2026-09-18',
                'time_slot': '10:00 AM - 11:00 AM',
                'payment_method': 'UPI',
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "This time slot has already passed for today")

    def test_popup_api_rejection_for_passed_slot(self):
        """
        Popup API must reject a booking for a slot whose time has crossed.
        """
        self.client.force_login(self.user)
        test_now = timezone.make_aware(datetime.datetime(2026, 9, 18, 14, 17, 0))
        with patch('django.utils.timezone.localtime', return_value=test_now):
            response = self.client.post("/api/popup-book-call/", {
                'full_name': 'Test User',
                'phone_number': '9876543210',
                'booking_date': '2026-09-18',
                'time_slot': '02:00 PM - 03:00 PM',
                'payment_method': 'UPI',
            })
            self.assertEqual(response.status_code, 400)
            data = response.json()
            self.assertFalse(data['success'])
            self.assertIn("already passed for today", data['message'])
