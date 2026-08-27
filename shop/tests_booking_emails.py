import datetime
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.core import mail
from shop.models import Product, CallBooking, CallSlot

@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class CallBookingEmailTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='localhost')
        self.product = Product.objects.create(
            name="Kanchipuram Pure Silk Saree",
            slug="kanchipuram-pure-silk-saree",
            sku="KPS-101",
            price=15000.00,
            stock=5
        )
        self.book_url = f"/shop/product/{self.product.slug}/book-call/"
        self.booking_date = (datetime.date.today() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')

    def test_1_booking_successfully_created(self):
        post_data = {
            'full_name': 'Priyanaka Verma',
            'email': 'priyanka@example.com',
            'phone_number': '+919876543210',
            'booking_date': self.booking_date,
            'time_slot': '10:00 AM - 11:00 AM',
            'notes': 'Show pink saree zari live'
        }
        response = self.client.post(self.book_url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        booking = CallBooking.objects.filter(product=self.product, phone_number='+919876543210').first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.full_name, 'Priyanaka Verma')
        self.assertEqual(booking.status, 'PENDING')
        self.assertTrue(booking.booking_reference.startswith('BK-'))

    def test_2_customer_confirmation_email(self):
        post_data = {
            'full_name': 'Meera Sundaram',
            'email': 'meera@example.com',
            'phone_number': '+919123456789',
            'booking_date': self.booking_date,
            'time_slot': '11:00 AM - 12:00 PM',
            'notes': 'Need assistance'
        }
        self.client.post(self.book_url, post_data)

        # 2 emails expected: 1 to customer, 1 to owner
        self.assertEqual(len(mail.outbox), 2)
        
        customer_email = [m for m in mail.outbox if 'meera@example.com' in m.to][0]
        self.assertEqual(customer_email.subject, 'Call Booking Confirmed - Rangam Saradha Silks')
        self.assertIn('Dear Meera Sundaram', customer_email.body)
        self.assertIn('Kanchipuram Pure Silk Saree', customer_email.body)
        self.assertIn(self.booking_date, customer_email.body)
        self.assertIn('11:00 AM - 12:00 PM', customer_email.body)

    def test_3_owner_notification_email(self):
        post_data = {
            'full_name': 'Ramesh Kumar',
            'email': 'ramesh@example.com',
            'phone_number': '+919988776655',
            'booking_date': self.booking_date,
            'time_slot': '02:00 PM - 03:00 PM',
            'notes': 'Checking bridal silk options'
        }
        self.client.post(self.book_url, post_data)

        owner_email = [m for m in mail.outbox if 'rangamsaradhasilks@gmail.com' in m.to][0]
        self.assertEqual(owner_email.subject, 'New Call Booking - Kanchipuram Pure Silk Saree')
        owner_text = owner_email.body
        self.assertIn('New customer call booking received', owner_text)
        self.assertIn('Ramesh Kumar', owner_text)
        self.assertIn('+919988776655', owner_text)
        self.assertIn('ramesh@example.com', owner_text)
        self.assertIn('Kanchipuram Pure Silk Saree', owner_text)
        self.assertIn('KPS-101', owner_text)
        self.assertIn('Checking bridal silk options', owner_text)
        self.assertIn('Customer has registered for a call regarding this particular saree.', owner_text)

    def test_4_booking_remains_saved_if_email_fails(self):
        post_data = {
            'full_name': 'Suresh Patel',
            'email': 'suresh@example.com',
            'phone_number': '+919776655443',
            'booking_date': self.booking_date,
            'time_slot': '04:00 PM - 05:00 PM',
            'notes': 'Test SMTP failure handling'
        }
        
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=Exception('SMTP Connection Error')):
            response = self.client.post(self.book_url, post_data, follow=True)
            self.assertEqual(response.status_code, 200)

        # Verify booking is STILL saved in database despite email failure
        booking = CallBooking.objects.filter(phone_number='+919776655443').first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.full_name, 'Suresh Patel')

    def test_5_no_duplicate_booking_or_email_on_resubmission(self):
        post_data = {
            'full_name': 'Kavitha Iyer',
            'email': 'kavitha@example.com',
            'phone_number': '+919443322110',
            'booking_date': self.booking_date,
            'time_slot': '06:00 PM - 07:00 PM',
            'notes': 'Duplicate test'
        }
        
        # First submission
        self.client.post(self.book_url, post_data)
        count_after_first = CallBooking.objects.filter(phone_number='+919443322110').count()
        emails_after_first = len(mail.outbox)
        self.assertEqual(count_after_first, 1)
        self.assertEqual(emails_after_first, 2)

        # Immediate resubmission with same details
        self.client.post(self.book_url, post_data)
        count_after_second = CallBooking.objects.filter(phone_number='+919443322110').count()
        emails_after_second = len(mail.outbox)

        self.assertEqual(count_after_second, 1)
        self.assertEqual(emails_after_second, 2)  # No duplicate email sent

    def test_6_empty_customer_email_still_notifies_owner(self):
        post_data = {
            'full_name': 'Anand Rao',
            'email': '',  # Empty customer email
            'phone_number': '+919554433221',
            'booking_date': self.booking_date,
            'time_slot': '10:00 AM - 11:00 AM',
            'notes': 'Customer did not enter email'
        }
        
        self.client.post(self.book_url, post_data)

        # 1 email expected (only to owner)
        self.assertEqual(len(mail.outbox), 1)
        owner_email = mail.outbox[0]
        self.assertIn('rangamsaradhasilks@gmail.com', owner_email.to)
        self.assertEqual(owner_email.subject, 'New Call Booking - Kanchipuram Pure Silk Saree')
        self.assertIn('Anand Rao', owner_email.body)

    def test_7_owner_blocked_slot_cannot_be_booked(self):
        # Owner blocks 10:00 AM - 11:00 AM for target date
        CallSlot.objects.create(
            date=self.booking_date,
            time_slot='10:00 AM - 11:00 AM',
            blocked_by_owner=True,
            status='BLOCKED',
            notes='Owner in meeting'
        )

        post_data = {
            'full_name': 'Customer Test',
            'email': 'customer@example.com',
            'phone_number': '+919876500000',
            'booking_date': self.booking_date,
            'time_slot': '10:00 AM - 11:00 AM',
        }
        response = self.client.post(self.book_url, post_data)
        # Should stay on page and show error message
        self.assertEqual(response.status_code, 200)
        self.assertIn('blocked by the owner', response.content.decode('utf-8'))

        # Ensure no booking was created
        booking = CallBooking.objects.filter(phone_number='+919876500000').first()
        self.assertIsNone(booking)

    def test_8_already_booked_slot_cannot_be_booked_again(self):
        # First booking succeeds
        post_data_1 = {
            'full_name': 'First Customer',
            'email': 'first@example.com',
            'phone_number': '+919876511111',
            'booking_date': self.booking_date,
            'time_slot': '11:00 AM - 12:00 PM',
        }
        self.client.post(self.book_url, post_data_1)
        self.assertEqual(CallBooking.objects.filter(time_slot='11:00 AM - 12:00 PM').count(), 1)

        # Second customer attempts to book same slot with different phone
        post_data_2 = {
            'full_name': 'Second Customer',
            'email': 'second@example.com',
            'phone_number': '+919876522222',
            'booking_date': self.booking_date,
            'time_slot': '11:00 AM - 12:00 PM',
        }
        response = self.client.post(self.book_url, post_data_2)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already been booked', response.content.decode('utf-8'))

        # Ensure second booking was rejected
        self.assertIsNone(CallBooking.objects.filter(phone_number='+919876522222').first())

    def test_9_cancelled_booking_releases_slot(self):
        # Create booking and then cancel it
        booking = CallBooking.objects.create(
            product=self.product,
            full_name='Third Customer',
            email='third@example.com',
            phone_number='+919876533333',
            booking_date=self.booking_date,
            time_slot='02:00 PM - 03:00 PM',
            status='CANCELLED'
        )

        # Now fourth customer books the same slot
        post_data = {
            'full_name': 'Fourth Customer',
            'email': 'fourth@example.com',
            'phone_number': '+919876544444',
            'booking_date': self.booking_date,
            'time_slot': '02:00 PM - 03:00 PM',
        }
        response = self.client.post(self.book_url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        fourth_booking = CallBooking.objects.filter(phone_number='+919876544444').first()
        self.assertIsNotNone(fourth_booking)

    def test_10_past_date_cannot_be_booked(self):
        past_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        post_data = {
            'full_name': 'Past Customer',
            'email': 'past@example.com',
            'phone_number': '+919876555555',
            'booking_date': past_date,
            'time_slot': '04:00 PM - 05:00 PM',
        }
        response = self.client.post(self.book_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('past', response.content.decode('utf-8').lower())

    def test_11_slot_availability_api_endpoint(self):
        # Block 1 slot
        CallSlot.objects.create(
            date=self.booking_date,
            time_slot='10:00 AM - 11:00 AM',
            blocked_by_owner=True,
            status='BLOCKED'
        )
        # Book 1 slot
        CallBooking.objects.create(
            product=self.product,
            full_name='Booked Customer',
            email='booked@example.com',
            phone_number='+919876566666',
            booking_date=self.booking_date,
            time_slot='11:00 AM - 12:00 PM',
            status='PENDING'
        )

        response = self.client.get(f'/shop/api/slot-availability/?date={self.booking_date}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['date'], self.booking_date)
        slots = {s['time_slot']: s for s in data['slots']}

        self.assertEqual(slots['10:00 AM - 11:00 AM']['status'], 'BLOCKED')
        self.assertFalse(slots['10:00 AM - 11:00 AM']['is_selectable'])

        self.assertEqual(slots['11:00 AM - 12:00 PM']['status'], 'BOOKED')
        self.assertFalse(slots['11:00 AM - 12:00 PM']['is_selectable'])

        self.assertEqual(slots['02:00 PM - 03:00 PM']['status'], 'AVAILABLE')
        self.assertTrue(slots['02:00 PM - 03:00 PM']['is_selectable'])

