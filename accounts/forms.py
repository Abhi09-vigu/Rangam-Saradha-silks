from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Address
from phonenumber_field.formfields import PhoneNumberField

class CountryCodePhoneWidget(forms.Widget):
    template_name = 'accounts/widgets/phone_input.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        country_code = '+91'
        mobile_number = ''
        if value:
            val_str = str(value).strip()
            if val_str.startswith('+'):
                codes = ['+91', '+1', '+44', '+61', '+971', '+65', '+966', '+60', '+49', '+33', '+81']
                found = False
                for code in codes:
                    if val_str.startswith(code):
                        country_code = code
                        mobile_number = val_str[len(code):].strip()
                        found = True
                        break
                if not found:
                    mobile_number = val_str.lstrip('+')
            else:
                mobile_number = val_str

        context['widget']['country_code'] = country_code
        context['widget']['mobile_number'] = mobile_number
        context['widget']['country_choices'] = [
            ('+91', '+91'),
            ('+1', '+1'),
            ('+44', '+44'),
            ('+61', '+61'),
            ('+971', '+971'),
            ('+65', '+65'),
            ('+966', '+966'),
            ('+60', '+60'),
            ('+49', '+49'),
            ('+33', '+33'),
            ('+81', '+81'),
        ]
        return context

    def value_from_datadict(self, data, files, name):
        mobile = data.get(f'{name}_mobile', '').strip()
        code = data.get(f'{name}_country', '+91').strip()
        full_phone = data.get(name, '').strip()

        clean_mobile = ''.join(c for c in mobile if c.isdigit())
        if clean_mobile:
            return f"{code}{clean_mobile}"
        elif full_phone:
            if not full_phone.startswith('+'):
                clean_digits = ''.join(c for c in full_phone if c.isdigit())
                if clean_digits:
                    return f"{code}{clean_digits}"
            return full_phone
        return ''

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email Address")
    phone_number = PhoneNumberField(
        required=False, 
        label="Phone Number (Optional)", 
        help_text="Optional mobile number for order tracking.",
        widget=CountryCodePhoneWidget()
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'phone_number':
                field.widget.attrs['class'] = 'form-control px-3 py-2'
            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Choose a unique username'
                field.label = 'Username'
            elif field_name == 'email':
                field.widget.attrs['placeholder'] = 'name@example.com'
                field.label = 'Email Address'
            elif field_name == 'phone_number':
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
    phone_number = PhoneNumberField(required=False, widget=CountryCodePhoneWidget())

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class AddressForm(forms.ModelForm):
    phone_number = PhoneNumberField(widget=CountryCodePhoneWidget())

    class Meta:
        model = Address
        fields = ('full_name', 'phone_number', 'address_line_1', 'address_line_2', 'city', 'state', 'pincode', 'landmark', 'address_type', 'is_default')
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
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

