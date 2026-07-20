from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Verify SMTP configuration by sending a test email.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Recipient email address')

    def handle(self, *args, **options):
        recipient = options['email']
        self.stdout.write(self.style.NOTICE(
            f"Attempting to send test email to {recipient} using SMTP Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}..."
        ))
        try:
            send_mail(
                subject='SMTP Configuration Test - Rangam Saradha Silks',
                message='Success! This is a test email sent from the Rangam Saradha Silks application verifying that the Gmail SMTP configuration works correctly.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Success! Test email sent successfully to {recipient}."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: Failed to send test email. Reason: {e}"))
