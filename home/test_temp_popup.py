from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from home.models import WebsiteSetting

User = get_user_model()
KOLKATA = ZoneInfo("Asia/Kolkata")

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
class TempPopupLaunchOverlayTests(TestCase):
    def setUp(self):
        # Create future target launch date
        self.future_date = datetime.now(KOLKATA) + timedelta(days=5)
        self.settings = WebsiteSetting.objects.create(
            website_name="Rangam Saradha Silk Sarees",
            launch_mode_active=True,
            launch_datetime=self.future_date,
            launch_title="Grand Opening Soon",
            launch_tagline_1="Something beautiful is about to begin.",
            launch_tagline_2="Tradition in Every Weave",
        )
        self.client = Client()

    def test_normal_visitor_sees_mandatory_overlay(self):
        """Normal customer must receive HTTP 200 with the full-screen mandatory overlay rendered over the page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="tempLaunchOverlay"')
        self.assertContains(response, 'temp-popup-active')
        self.assertContains(response, 'Grand Opening Soon')
        self.assertContains(response, 'Something beautiful is about to begin.')
        self.assertContains(response, 'Tradition in Every Weave')
        self.assertContains(response, 'tempCountdownGrid')
        # Check that underlying page elements are rendered in DOM behind overlay
        self.assertContains(response, 'navbar-premium')

    def test_admin_staff_bypass_authenticated(self):
        """Staff users must NEVER see the launch overlay."""
        staff_user = User.objects.create_user(
            username="admin_user",
            password="adminpassword123",
            is_staff=True
        )
        self.client.force_login(staff_user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="tempLaunchOverlay"')
        self.assertNotContains(response, 'temp-popup-active')

    def test_admin_staff_bypass_admin_session_cookie(self):
        """Users with an active admin_sessionid cookie bypass the overlay."""
        staff_user = User.objects.create_user(
            username="staff_cookie_user",
            password="password123",
            is_staff=True
        )
        session = SessionStore()
        session['_auth_user_id'] = str(staff_user.pk)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session.save()

        client = Client()
        client.cookies['admin_sessionid'] = session.session_key
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="tempLaunchOverlay"')
        self.assertNotContains(response, 'temp-popup-active')

    def test_admin_disables_temp_popup(self):
        """Turning launch_mode_active OFF immediately lifts the overlay for everyone."""
        self.settings.launch_mode_active = False
        self.settings.save()

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="tempLaunchOverlay"')
        self.assertNotContains(response, 'temp-popup-active')

    def test_past_datetime_automatically_lifts_overlay(self):
        """When the launch datetime has passed, the overlay is automatically inactive."""
        self.settings.launch_datetime = datetime.now(KOLKATA) - timedelta(minutes=10)
        self.settings.save()

        self.assertFalse(self.settings.is_temp_popup_active)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="tempLaunchOverlay"')
        self.assertNotContains(response, 'temp-popup-active')
