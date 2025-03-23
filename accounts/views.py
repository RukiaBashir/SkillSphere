import random

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model, authenticate, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView, TemplateView, FormView
from twilio.rest import Client

from SkillSphere import settings
from classes.models import Class
from notifications.models import Notification
from notifications.utils import send_sms
from payments.models import CartItem
from .forms import OTPForm, SkillUserRegisterForm, UserProfileUpdateForm, BecomeInstructorForm
from .models import SkillUser

from twilio.base.exceptions import TwilioRestException
import phonenumbers


def format_phone_number(phone_number):
    """ Ensure the phone number is in E.164 format """
    parsed = phonenumbers.parse(phone_number, "KE")  # 'KE' for Kenya
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def register(request):
    if request.method == 'POST':
        form = SkillUserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.country = form.cleaned_data.get('country', '')
            user.is_active = False  # User remains inactive until OTP is verified.
            user.save()

            otp = random.randint(100000, 999999)
            request.session['otp'] = otp
            request.session['user_id'] = user.id


            send_mail(
                'Your OTP Code for SkillSphere',
                f'Your OTP Code is {otp}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
            print(f'Your SkillSphere OTP Code is {otp}')

            if user.phone_number:
                try:
                    formatted_number = format_phone_number(user.phone_number)
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    client.messages.create(
                        body=f'Your SkillSphere OTP Code is {otp}',
                        messaging_service_sid=settings.TWILIO_MESSAGING_SERVICE_SID,  # Use Messaging Service
                        to=formatted_number
                    )
                except TwilioRestException as e:
                    print(f"Twilio Error: {e}")

            if user.role == 'instructor':
                messages.info(request,
                              """Thank you for registering as an instructor. Please complete your instructor
                              registration by paying the registration fee (minimum KES 100.00) on the instructor
                              payment page.""")

            return redirect('accounts:verify_otp')
    else:
        form = SkillUserRegisterForm()
    return render(request, 'register.html', {'form': form})


class BecomeInstructorView(LoginRequiredMixin, FormView):
    """
    Displays a form for a user to confirm that they want to become an instructor.
    On submission, creates a CartItem record for the instructor registration fee
    (with no associated class) and redirects the user to the instructor payment form.
    """
    template_name = "users/become_instructor.html"
    form_class = BecomeInstructorForm
    success_url = reverse_lazy("payments:cart-list")  # Redirect to the payment form
    login_url = 'accounts:login'

    def form_valid(self, form):
        fee_amount = getattr(settings, "INSTRUCTOR_REGISTRATION_FEE", 100.00)
        user = self.request.user

        # Create a CartItem for the instructor registration fee (no class associated)
        cart_item, created = CartItem.objects.get_or_create(
            user=user,
            class_booking=None,
            defaults={
                "amount": fee_amount,
                "payment_status": "pending",
            }
        )
        messages.success(
            self.request,
            "Instructor registration initiated. Please complete payment to activate your instructor account."
        )
        return super().form_valid(form)


class InstructorPaymentSuccessView(TemplateView):
    """
    Simulates a successful payment callback for instructor registration.
    Once payment is successful, the view updates the user's role and instructor_status,
    marks the instructor registration Payment as completed, and creates a notification.
    """
    template_name = "users/instructor_payment_success.html"

    def get(self, request, *args, **kwargs):
        user = request.user

        # Update the user to become an instructor and set instructor_status to active.
        if user.role != "instructor":
            user.role = "instructor"
        user.instructor_status = "active"
        user.save()

        # Find the pending Payment record for instructor registration (class_booking is null)
        try:
            payment = CartItem.objects.get(user=user, class_booking__isnull=True, payment_status='pending')
            payment.payment_status = 'completed'
            payment.save()

            # Create a notification for the successful payment.
            Notification.objects.create(
                user=user,
                payment=payment,
                message=f"Your payment for the instructor registration fee of KES {payment.amount} has been completed successfully."
            )
        except CartItem.DoesNotExist:
            # Handle the case when no pending payment is found (e.g., log the event).
            pass

        messages.success(request, "Your instructor account is now active!")
        return super().get(request, *args, **kwargs)


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillUser
    form_class = UserProfileUpdateForm
    template_name = 'users/profile.html'
    success_url = reverse_lazy('accounts:profile')  # Adjust namespace/name as needed

    def get_object(self, queryset=None):
        # Return the logged-in user
        return self.request.user

    def get_form_kwargs(self):
        """ Pass the current user to the form to control field visibility and initial values. """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There were errors updating your profile. Please correct them and try again.")
        return super().form_invalid(form)


# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('classes:class-list')
        else:
            messages.error(request, 'Invalid credentials')
    return render(request, 'login.html')


# Logout view
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# Forgot password view
def forgot_password(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                email_template_name='users/password_reset_email.html',
                subject_template_name='users/password_reset_subject.txt',
            )
            messages.success(request, 'Password reset email sent!')
            return redirect('login')
        else:
            messages.error(request, 'Error sending email')
    else:
        form = PasswordResetForm()
    return render(request, 'users/forgot_password.html', {'form': form})


def verify_otp(request):
    """
    Verifies OTP and redirects users to their respective dashboards.
    """
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data.get('otp')
            if int(otp_entered) == request.session.get('otp'):
                user_id = request.session.get('user_id')
                user = SkillUser.objects.get(id=user_id)
                user.is_active = True
                user.save()

                # Log in user
                login(request, user)
                messages.success(request, "Your account has been activated!")

                # Redirect based on role
                if user.role == 'instructor':
                    return redirect('accounts:instructor-dashboard')
                else:
                    return redirect('accounts:learner-dashboard')

            messages.error(request, "Invalid OTP. Please try again.")
    else:
        form = OTPForm()

    return render(request, 'users/verify_otp.html', {'form': form})


class LearnerDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Class
    template_name = 'learner_dashboard.html'
    context_object_name = 'classes'

    def test_func(self):
        # Allow both instructors and learners to access the dashboard.
        return self.request.user.role in ['instructor', 'learner']

    # Redirect to the login page if the user doesn't have permission
    def handle_no_permission(self):
        return redirect('accounts:login')

    def get_queryset(self):
        # Get all available classes
        return Class.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all purchased classes for the logged-in learner
        purchased_classes = Class.objects.filter(enrollments__learner=self.request.user)

        context['purchased_classes'] = purchased_classes
        return context


class InstructorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "instructor_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instructor = self.request.user

        # Get all classes owned by the instructor
        classes_owned = Class.objects.filter(instructor=instructor)
        context['total_classes'] = classes_owned.count()

        # Ongoing and coming soon classes
        context['ongoing_classes'] = classes_owned.filter(status='ongoing').count()
        context['coming_soon_classes'] = classes_owned.filter(status='coming_soon').count()

        # Count learners who have completed payments for these classes.
        context['learners_count'] = CartItem.objects.filter(
            class_booking__in=classes_owned, payment_status='completed'
        ).values('user').distinct().count()

        # Check if the instructor has completed the payment
        instructor_payment = CartItem.objects.filter(
            user=instructor, class_booking__isnull=True, payment_status='completed'
        ).exists()

        context['instructor_paid'] = instructor_payment
        return context
