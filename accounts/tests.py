from django.test import TestCase, Client
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


