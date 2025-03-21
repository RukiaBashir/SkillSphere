from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import DateInput
from phonenumber_field.formfields import PhoneNumberField

from accounts.models import Feedback, SkillUser


class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6, label="Enter OTP")


class SkillUserRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=255, required=True)
    last_name = forms.CharField(max_length=255, required=True)
    specialization = forms.CharField(max_length=100, required=False)
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    username = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone_number = PhoneNumberField(
        region="GB",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. +12345678901'})
    )
    role = forms.ChoiceField(
        choices=[('learner', 'Learner'), ('instructor', 'Instructor')],
        required=True,
        widget=forms.Select(attrs={'id': 'id_role'})
    )
    profile_image = forms.ImageField(required=False)
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput, required=True)

    class Meta:
        model = get_user_model()
        fields = (
            'first_name', 'last_name', 'specialization', 'birth_date',
            'username', 'email', 'phone_number', 'role', 'profile_image',
            'password1', 'password2'
        )

    widgets = {
        'birth_date': forms.DateTimeInput(attrs={'type': 'date'}),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Loop through all fields and add 'is-invalid' if there are errors.
        for field_name, field in self.fields.items():
            if self.errors.get(field_name):
                existing_classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{existing_classes} is-invalid"

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match.")
        return password2

    def clean_email(self):
        email = self.cleaned_data['email']
        UserModel = get_user_model()
        if UserModel.objects.filter(email=email).exists():
            raise ValidationError('Email already exists.')
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and len(str(phone_number)) < 10:
            raise ValidationError('Please enter a valid phone number.')
        return phone_number


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = SkillUser
        fields = [
            'first_name',
            'last_name',
            'specialization',
            'birth_date',
            'phone_number',
            'profile_image'
        ]
        widgets = {
            'birth_date': DateInput(attrs={'type': 'date'})
        }

    def __init__(self, *args, **kwargs):
        # Get user instance passed from the view
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Hide specialization for learners
        if user and user.role == "learner":
            self.fields["specialization"].widget = forms.HiddenInput()
            self.fields["specialization"].required = False

        # For the birth_date field, set value from instance if exists; else set placeholder.
        if self.instance and self.instance.birth_date:
            self.fields['birth_date'].widget.attrs.update({
                'value': self.instance.birth_date.strftime('%Y-%m-%d')
            })
        else:
            self.fields['birth_date'].widget.attrs.update({
                'placeholder': 'YYYY-MM-DD'
            })

        # Prepopulate other text fields with current value or a placeholder.
        for field in ['first_name', 'last_name', 'phone_number']:
            current_value = getattr(self.instance, field, None)
            if current_value:
                self.fields[field].widget.attrs.update({
                    'value': current_value
                })
            else:
                self.fields[field].widget.attrs.update({
                    'placeholder': f'Enter {field.replace("_", " ")}'
                })


class USerPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label='Email',
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'})
    )


class BecomeInstructorForm(forms.Form):
    confirm = forms.BooleanField(
        label="I confirm that I want to become an instructor and pay the registration fee.",
        required=True
    )


class ContactForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ('f_name', 'f_email', 'f_message')

    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column(Field('f_name', css_class='col-md-4'), css_class='form-group', ),
                Column(Field('f_email', css_class='col-md-4'), css_class='form-group'),
                Column(Field('f_message', css_class='col-md-4'), css_class='form-group'),
            ),
        )
