import random

from _socket import gaierror
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.views.generic import UpdateView, FormView
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from SkillSphere import settings
from accounts.models import SkillUser, Feedback, SiteConfiguration
from classes.models import Class, Enrollment, SkillCategory
from notifications.models import Notification
from payments.models import CartItem, Order
from .forms import OTPForm, UserProfileUpdateForm, BecomeInstructorForm, SetNewPasswordForm
from .forms import SkillUserRegisterForm
from django.utils.timezone import now


def format_phone_number(phone_number):
    if not phone_number.startswith('+'):
        return f'+{phone_number}'
    return phone_number


def register(request):
    if request.method == 'POST':
        form = SkillUserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.country = form.cleaned_data.get('country', '')
                user.is_active = False  # Inactive until OTP verification
                user.save()

                otp = random.randint(100000, 999999)
                request.session['otp'] = otp
                request.session['user_id'] = user.id

                # Send OTP via email
                send_mail(
                    'Your OTP Code for SkillSphere',
                    f'Your OTP Code is {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )

                print(f'Generated OTP: {otp}')

                # Send OTP via SMS using Twilio Verify
                if user.phone_number:
                    formatted_number = format_phone_number(user.phone_number)
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

                    client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                        .verifications.create(to=formatted_number, channel='sms')

                    print(f"OTP sent to {formatted_number}")

                # Instructor-specific message
                if user.role == 'instructor':
                    messages.info(request,
                                  """Thank you for registering as an instructor. Please complete your instructor
                    registration by paying the registration fee (minimum KES 100.00) on the instructor
                    payment page."""
                                  )

                return redirect('accounts:verify_otp')

            except (gaierror, TwilioRestException) as e:
                print(f"Error: {e}")
                messages.error(request, "Sorry, an error occurred. Please try again.")
                return render(request, 'register.html', {'form': form, 'show_error_modal': True})
    else:
        form = SkillUserRegisterForm()

    return render(request, 'register.html', {'form': form})


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillUser
    form_class = UserProfileUpdateForm
    template_name = 'users/profile.html'
    success_url = reverse_lazy('accounts:login')

    def get_object(self, queryset=None):
        # Return the logged-in user.
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass current user to the form.
        return kwargs

    def form_valid(self, form):
        otp_entered = form.cleaned_data.get('otp')
        session_otp = self.request.session.get('otp')
        if not session_otp or str(otp_entered) != str(session_otp):
            messages.error(self.request, "Invalid OTP. Please try again.")
            return self.form_invalid(form)
        self.request.session.pop('otp', None)
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
    """
    Sends OTP via email or Twilio for password reset.
    """
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Check if user with provided email exists
            try:
                user = SkillUser.objects.get(email=email, is_active=True)
            except SkillUser.DoesNotExist:
                messages.error(request, "No active user found with that email.")
                return redirect('accounts:forgot-password')

            # Generate OTP and store it in the session
            otp = random.randint(100000, 999999)
            request.session['user_id'] = user.id
            request.session['otp'] = otp

            # Send OTP via email
            form.save(
                request=request,
                email_template_name='users/password_reset_email.html',
                subject_template_name='users/password_reset_subject.txt',
                extra_email_context={'otp': otp}  # Pass the OTP to the email context
            )

            # Send OTP via Twilio (if phone_number exists)
            if user.phone_number:
                try:
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                        .verifications.create(to=user.phone_number, channel="sms")
                except TwilioRestException as e:
                    print(f"Twilio Error: {e}")
                    messages.warning(request, "Failed to send OTP via SMS. Check phone number or Twilio settings.")

            # Notify user and redirect to OTP verification
            messages.success(request, 'An OTP has been sent to your email and phone (if provided).')
            return redirect('accounts:verify_otp_password')
    else:
        form = PasswordResetForm()

    return render(request, 'users/forgot_password.html', {'form': form})


def verify_otp_password(request):
    """
    Verifies OTP for password reset.
    Supports email and Twilio OTP verification.
    """
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data.get('otp')
            valid = False

            # Get session variables
            session_otp = request.session.get('otp')
            user_id = request.session.get('user_id')

            if not user_id:
                messages.error(request, "Session expired. Please try again.")
                return redirect('accounts:forgot-password')

            user = get_object_or_404(SkillUser, id=user_id)

            # Validate OTP (Email OTP check)
            if session_otp and str(otp_entered) == str(session_otp):
                valid = True
            else:
                # Validate Twilio OTP if phone_number exists
                if user.phone_number:
                    try:
                        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                        verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                            .verification_checks.create(to=user.phone_number, code=otp_entered)
                        if verification_check.status == 'approved':
                            valid = True
                    except TwilioRestException as e:
                        print(f"Twilio Verification Error: {e}")

            if valid:
                # Store verified user for password reset
                request.session['verified_user_id'] = user.id
                return redirect('accounts:set_new_password')
            else:
                messages.error(request, "Invalid OTP. Please try again.")

    else:
        form = OTPForm()

    return render(request, 'users/verify_otp_password.html', {'form': form})


def set_new_password(request):
    """
    Allows users to set a new password after successful OTP verification.
    """
    user_id = request.session.get('verified_user_id')

    if not user_id:
        messages.error(request, "Session expired. Please verify OTP again.")
        return redirect('accounts:forgot-password')

    user = get_object_or_404(SkillUser, id=user_id)

    if request.method == 'POST':
        form = SetNewPasswordForm(user, request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.password = make_password(new_password)
            user.save()

            # Clear session after password reset
            request.session.pop('verified_user_id', None)
            request.session.pop('otp', None)
            request.session.pop('user_id', None)

            # Automatically log the user in after password reset
            login(request, user)

            messages.success(request, "Your password has been reset successfully!")
            return redirect('accounts:login')

    else:
        form = SetNewPasswordForm(user)

    return render(request, 'users/set_new_password.html', {'form': form})


def verify_otp(request):
    """
    Verifies OTP and redirects users to their respective dashboards.
    Validates if either the custom email OTP or the Twilio Verify OTP is correct.
    """
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data.get('otp')
            valid = False

            # First, check if the entered OTP matches the one sent via email
            session_otp = request.session.get('otp')
            if session_otp and str(otp_entered) == str(session_otp):
                valid = True
            else:
                # If email OTP doesn't match, try Twilio Verify OTP check
                user_id = request.session.get('user_id')
                if not user_id:
                    messages.error(request, "Session expired. Please register again.")
                    return redirect('accounts:register')

                user = get_object_or_404(SkillUser, id=user_id)
                if user.phone_number:
                    try:
                        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                        verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                            .verification_checks.create(to=user.phone_number, code=otp_entered)
                        if verification_check.status == 'approved':
                            valid = True
                    except TwilioRestException as e:
                        print(f"Twilio Verification Error: {e}")
                        valid = False

            if valid:
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
            else:
                messages.error(request, "Invalid OTP. Please try again.")
    else:
        form = OTPForm()

    return render(request, 'users/verify_otp.html', {'form': form})


@login_required(login_url='accounts:login')  # Redirects anonymous users to /login/
def dashboard_redirect(request):
    if request.user.is_superuser:
        return redirect('accounts:admin-dashboard')
    elif request.user.role == 'instructor':
        return redirect('classes:dashboard')
    else:
        return redirect('accounts:learner-dashboard')


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


class LearnerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "learner_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get recent notifications (e.g., last 5)
        context['notifications'] = Notification.objects.filter(user=self.request.user).order_by('-created_at')[:5]
        # Get enrolled/purchased classes
        context['enrollments'] = Enrollment.objects.filter(learner=self.request.user, is_paid=True)
        return context


class InstructorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "instructor_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instructor = self.request.user

        # Get all classes owned by the instructor
        classes_owned = Class.objects.filter(instructor=instructor)

        # Update class statuses dynamically
        for class_obj in classes_owned:
            if class_obj.schedule > now():
                class_obj.status = 'coming_soon'
            elif class_obj.schedule <= now() and class_obj.is_active:
                class_obj.status = 'ongoing'
            else:
                class_obj.status = 'completed'
            class_obj.save(update_fields=['status'])

        # Update context for the dashboard
        context['classes'] = classes_owned
        context['total_classes'] = classes_owned.count()
        context['ongoing_classes'] = classes_owned.filter(status='ongoing').count()
        context['coming_soon_classes'] = classes_owned.filter(status='coming_soon').count()
        context['completed_classes'] = classes_owned.filter(status='completed').count()
        context['learners_count'] = CartItem.objects.filter(
            class_booking__in=classes_owned,
            payment_status='completed'
        ).values('user').distinct().count()

        # Check if the instructor registration fee is paid
        context['instructor_paid'] = CartItem.objects.filter(
            user=instructor,
            class_booking__isnull=True,
            payment_status='completed'
        ).exists()

        return context

class AdminDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "admin_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # User statistics
        context['total_users'] = SkillUser.objects.count()
        context['total_instructors'] = SkillUser.objects.filter(role='instructor').count()
        context['total_active_instructors'] = SkillUser.objects.filter(role='instructor',
                                                                       instructor_status='active').count()
        context['total_learners'] = SkillUser.objects.filter(role='learner').count()

        # Class statistics
        context['total_classes'] = Class.objects.count()
        context['approved_classes'] = Class.objects.filter(is_approved=True).count()
        context['pending_classes'] = Class.objects.filter(is_approved=False).count()
        context['ongoing_classes'] = Class.objects.filter(status='ongoing').count()

        # Category statistics
        context['total_categories'] = SkillCategory.objects.count()
        context['categories_with_classes'] = SkillCategory.objects.filter(classes__isnull=False).distinct().count()

        # Enrollment statistics
        context['total_enrollments'] = Enrollment.objects.count()
        context['paid_enrollments'] = Enrollment.objects.filter(is_paid=True).count()
        context['booked_enrollments'] = Enrollment.objects.filter(is_booked=True).count()

        # Order statistics
        context['total_orders'] = Order.objects.count()
        context['total_revenue'] = Order.objects.aggregate(total=models.Sum('total'))['total'] or 0

        # Cart statistics
        context['pending_cart_items'] = CartItem.objects.filter(payment_status='pending').count()
        context['completed_cart_items'] = CartItem.objects.filter(payment_status='completed').count()

        # Site Configuration
        context['site_config'] = SiteConfiguration.objects.first()

        # Feedback statistics
        context['total_feedbacks'] = Feedback.objects.count()

        return context


@login_required
@require_GET
def request_otp(request):
    """
    Sends an OTP to the logged-in user's email and phone number.
    """
    user = request.user
    otp = random.randint(100000, 999999)
    request.session['otp'] = str(otp)

    # Send OTP via email
    send_mail(
        'Your OTP Code for SkillSphere',
        f'Your OTP Code is {otp}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

    # Send OTP via SMS using Twilio Verify (or your preferred method)
    if user.phone_number:
        try:
            formatted_number = format_phone_number(user.phone_number)
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verifications.create(to=formatted_number, channel='sms')
        except TwilioRestException as e:
            # Log or return an error as needed.
            return JsonResponse({"error": f"Twilio Error: {e}"}, status=500)

    return JsonResponse({"message": "OTP has been sent."})
