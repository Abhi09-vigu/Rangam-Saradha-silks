from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
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
    first_name = forms.CharField(
        max_length=150, 
        required=True, 
        label="First Name",
        widget=forms.TextInput(attrs={'placeholder': 'Enter first name', 'class': 'form-input-control', 'required': True})
    )
    last_name = forms.CharField(
        max_length=150, 
        required=False, 
        label="Last Name",
        widget=forms.TextInput(attrs={'placeholder': 'Enter last name', 'class': 'form-input-control'})
    )
    email = forms.EmailField(
        required=True, 
        label="Email Address",
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address', 'class': 'form-input-control', 'required': True})
    )
    phone_number = PhoneNumberField(
        required=True, 
        label="Mobile Number", 
        help_text="Mobile number is mandatory for order updates and verification.",
        widget=CountryCodePhoneWidget(attrs={'required': True}),
        error_messages={'required': 'Mobile number is mandatory.'}
    )
    agree_terms = forms.BooleanField(
        required=True, 
        error_messages={'required': 'You must agree to the Terms & Conditions and Privacy Policy.'}
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].required = False
            self.fields['username'].widget.attrs['placeholder'] = 'Choose a unique username'
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs['placeholder'] = 'Create a password'
            self.fields['password1'].widget.attrs['class'] = 'form-input-control'
            self.fields['password1'].label = 'Password'
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs['placeholder'] = 'Confirm your password'
            self.fields['password2'].widget.attrs['class'] = 'form-input-control'
            self.fields['password2'].label = 'Confirm Password'

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if username:
            if CustomUser.objects.filter(username__iexact=username).exists():
                raise forms.ValidationError("A user with that username already exists.")
            return username
        return ''

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("Email address is mandatory.")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists with this email address. Please log in.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            raise forms.ValidationError("Mobile number is mandatory.")
        
        phone_str = str(phone_number).strip()
        digits = ''.join(c for c in phone_str if c.isdigit())
        
        # Check if phone number already belongs to an existing user
        existing_user = CustomUser.objects.filter(phone_number=phone_number).first()
        if not existing_user and len(digits) >= 10:
            existing_user = CustomUser.objects.filter(phone_number__endswith=digits[-10:]).first()
            
        if existing_user:
            raise forms.ValidationError("An account already exists with this mobile number. A mobile number cannot be registered with multiple emails.")
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number')
        if phone_number:
            phone_str = str(phone_number).strip()
            digits = ''.join(c for c in phone_str if c.isdigit())
            existing_user = CustomUser.objects.filter(phone_number=phone_number).first()
            if not existing_user and len(digits) >= 10:
                existing_user = CustomUser.objects.filter(phone_number__endswith=digits[-10:]).first()
            if existing_user:
                self.add_error('phone_number', "An account already exists with this mobile number.")

        username = cleaned_data.get('username')
        email = cleaned_data.get('email')
        first_name = cleaned_data.get('first_name', '')
        if not username:
            import re, uuid
            base = ''
            if email:
                base = email.split('@')[0].lower()
                base = re.sub(r'[^a-zA-Z0-9_]', '', base)
            if not base and first_name:
                base = re.sub(r'[^a-zA-Z0-9_]', '', first_name.lower().replace(' ', ''))
            if not base:
                base = 'customer'
            candidate = base
            while CustomUser.objects.filter(username__iexact=candidate).exists():
                candidate = f"{base}_{uuid.uuid4().hex[:4]}"
            cleaned_data['username'] = candidate
            self.cleaned_data['username'] = candidate
            if hasattr(self, '_errors') and 'username' in self._errors:
                del self._errors['username']

        return cleaned_data

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone_number', 'is_verified')

class UserProfileForm(forms.ModelForm):
    phone_number = PhoneNumberField(
        required=True,
        widget=CountryCodePhoneWidget(attrs={'required': True}),
        error_messages={'required': 'Mobile number is mandatory.'}
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email Address'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'phone_number':
                field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email:
            qs = CustomUser.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("An account already exists with this email address.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            raise forms.ValidationError("Mobile number is mandatory.")
        phone_str = str(phone_number).strip()
        digits = ''.join(c for c in phone_str if c.isdigit())
        qs = CustomUser.objects.filter(phone_number=phone_number)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An account already exists with this mobile number.")
        if len(digits) >= 10:
            qs_end = CustomUser.objects.filter(phone_number__endswith=digits[-10:])
            if self.instance and self.instance.pk:
                qs_end = qs_end.exclude(pk=self.instance.pk)
            if qs_end.exists():
                raise forms.ValidationError("An account already exists with this mobile number.")
        return phone_number



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


class CompletePhoneForm(forms.Form):
    phone_number = PhoneNumberField(
        required=True,
        label="Mobile Number",
        help_text="Please enter a valid mobile number for your account.",
        widget=CountryCodePhoneWidget(attrs={'required': True}),
        error_messages={'required': 'Mobile number is mandatory.'}
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            raise forms.ValidationError("Mobile number is mandatory.")

        phone_str = str(phone_number).strip()
        digits = ''.join(c for c in phone_str if c.isdigit())

        qs = CustomUser.objects.filter(phone_number=phone_number)
        if self.user and self.user.pk:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError(
                "An account already exists with this mobile number. A mobile number cannot be registered with multiple emails."
            )

        if len(digits) >= 10:
            qs_end = CustomUser.objects.filter(phone_number__endswith=digits[-10:])
            if self.user and self.user.pk:
                qs_end = qs_end.exclude(pk=self.user.pk)
            if qs_end.exists():
                raise forms.ValidationError(
                    "An account already exists with this mobile number. A mobile number cannot be registered with multiple emails."
                )

        return phone_number


class SetAccountPasswordForm(forms.Form):
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-control',
            'placeholder': 'Create account password',
            'required': True
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-control',
            'placeholder': 'Confirm your password',
            'required': True
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password, self.user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match. Please re-enter.")
        return cleaned_data

    def save(self, commit=True):
        password = self.cleaned_data['password']
        self.user.set_password(password)
        if commit:
            self.user.save(update_fields=['password'])
        return self.user


