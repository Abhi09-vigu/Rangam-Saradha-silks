from rest_framework import serializers
from .models import ContactMessage

class ContactMessageSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Name is required.',
            'blank': 'Name cannot be blank.'
        }
    )
    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Valid email is required.',
            'invalid': 'Valid email is required.',
            'blank': 'Valid email is required.'
        }
    )
    subject = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Subject is required.',
            'blank': 'Subject cannot be blank.'
        }
    )
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Message is required.',
            'blank': 'Message cannot be blank.'
        }
    )

    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
