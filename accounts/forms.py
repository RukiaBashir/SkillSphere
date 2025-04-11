from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.forms import DateInput
from phonenumber_field.formfields import PhoneNumberField

from accounts.models import Feedback, SkillUser


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
            'username', 'email', 'phone_number', 'role', 
            'local_image',
            'external_image_url',
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
    # Account credentials fields
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep the current password."
    )
    otp = forms.CharField(
        max_length=6,
        required=False,
        help_text="Enter the OTP sent to your email for account verification."
    )

    class Meta:
        model = SkillUser
        fields = [
            'first_name',
            'last_name',
            'specialization',
            'birth_date',
            'phone_number',
            'local_image',
            'external_image_url'
        ]
        widgets = {
            'birth_date': DateInput(attrs={'type': 'date'})
        }

    def __init__(self, *args, **kwargs):
        # Get the current user instance from the view
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Prepopulate account fields from the user object
        self.fields['username'].initial = user.username if user else ''
        self.fields['email'].initial = user.email if user else ''

        # Hide specialization for learners
        if user and user.role == "learner":
            self.fields["specialization"].widget = forms.HiddenInput()
            self.fields["specialization"].required = False

        # For the birth_date field, set its value from the instance if available
        if self.instance and self.instance.birth_date:
            self.fields['birth_date'].widget.attrs.update({
                'value': self.instance.birth_date.strftime('%Y-%m-%d')
            })
        else:
            self.fields['birth_date'].widget.attrs.update({
                'placeholder': 'YYYY-MM-DD'
            })

        # Prepopulate other fields with current values or placeholders.
        for field in ['first_name', 'last_name', 'phone_number']:
            current_value = getattr(self.instance, field, None)
            if current_value:
                self.fields[field].widget.attrs.update({'value': current_value})
            else:
                self.fields[field].widget.attrs.update({'placeholder': f'Enter {field.replace("_", " ")}'})

    def clean_email(self):
        email = self.cleaned_data.get("email")
        # Exclude the current instance so that updating to the same email is allowed.
        if SkillUser.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if SkillUser.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        # Optionally, implement any phone number validation here.
        if SkillUser.objects.exclude(pk=self.instance.pk).filter(phone_number=phone_number).exists():
            raise ValidationError("This phone number is already in use.")
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        # Add any OTP validation logic if needed.
        # For example:
        # otp_input = cleaned_data.get('otp')
        # if not otp_input or otp_input != self.instance.profile.otp_code:
        #     raise ValidationError("Invalid OTP provided for account update.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        # Update account credentials from the cleaned data
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data["email"]
        new_password = self.cleaned_data.get("new_password")
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user


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


class OTPForm(forms.Form):
    otp = forms.CharField(
        label='Enter OTP',
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter OTP'
        })
    )


class OTPFormPassword(forms.Form):
    otp = forms.CharField(
        label='Enter OTP',
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter OTP'
        })
    )


class SetNewPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    new_password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
