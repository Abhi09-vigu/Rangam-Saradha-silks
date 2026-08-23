from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Address
from phonenumber_field.formfields import PhoneNumberField

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email Address")
    phone_number = PhoneNumberField(required=False, label="Phone Number (Optional)", help_text="Optional mobile number for order tracking.")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control px-3 py-2'
            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Choose a unique username'
                field.label = 'Username'
            elif field_name == 'email':
                field.widget.attrs['placeholder'] = 'name@example.com'
                field.label = 'Email Address'
            elif field_name == 'phone_number':
                field.widget.attrs['placeholder'] = '+91 9876543210'
                field.label = 'Phone Number (Optional)'
            elif field_name == 'password1':
                field.widget.attrs['placeholder'] = 'Create a strong password'
                field.label = 'Password'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Confirm your password'
                field.label = 'Confirm Password'

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and CustomUser.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("A user with this phone number already exists.")
        return phone_number

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone_number', 'is_verified')

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ('full_name', 'phone_number', 'address_line_1', 'address_line_2', 'city', 'state', 'pincode', 'landmark', 'address_type', 'is_default')
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'House No., Building, Street Name'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Colony, Area, Sector (Optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pincode'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Landmark (Optional)'}),
            'address_type': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(max_length=6, widget=forms.TextInput(attrs={'class': 'form-control text-center fs-2 fw-bold', 'placeholder': '------'}))

class ForgotPasswordForm(forms.Form):
    email_or_phone = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email or Phone Number'}))

class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}))

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class PhoneLoginForm(forms.Form):
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10-digit mobile number',
            'type': 'tel',
            'pattern': '[6-9][0-9]{9}',
            'required': 'true'
        })
    )

    def clean_phone_number(self):
        raw_number = self.cleaned_data.get('phone_number')
        # Remove any spaces, dashes, or parentheses
        cleaned_number = ''.join(c for c in raw_number if c.isdigit())
        if len(cleaned_number) == 10:
            full_number = f"+91{cleaned_number}"
        elif len(cleaned_number) == 12 and cleaned_number.startswith('91'):
            full_number = f"+{cleaned_number}"
        else:
            raise forms.ValidationError("Please enter a valid 10-digit Indian mobile number.")
        
        # Now parse it using phonenumbers to verify
        import phonenumbers
        try:
            parsed = phonenumbers.parse(full_number, None)
            if not phonenumbers.is_valid_number(parsed):
                raise forms.ValidationError("Invalid phone number format.")
        except Exception:
            raise forms.ValidationError("Invalid phone number format.")
            
        return full_number

