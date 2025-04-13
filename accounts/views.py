import random

from _socket import gaierror
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.formats import localize
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.views.generic import UpdateView, FormView
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from SkillSphere import settings
from SkillSphere.utils.supabase_upload import upload_to_supabase
from accounts.models import SkillUser, Feedback, SiteConfiguration
from classes.models import Class, Enrollment, SkillCategory
from notifications.models import Notification
from payments.models import CartItem, Order
from .forms import OTPForm, UserProfileUpdateForm, BecomeInstructorForm, SetNewPasswordForm, OTPFormPassword
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
                # Upload profile image to Supabase
                profile_image_file = request.FILES.get('profile_image')
                if profile_image_file:
                    uploaded_url = upload_to_supabase_s3(profile_image_file, folder='profile_images')
                    user.external_image_url = uploaded_url
                    user.local_image = None  # clear local if using external
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
        # Handle Supabase upload for profile_image
        image_file = self.request.FILES.get('profile_image')
        if image_file:
            public_url = upload_to_supabase(image_file, folder='profile_images')
            form.instance.external_profile_image_url = public_url
            form.instance.profile_image = None  # Optionally clear local field
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
    Sends OTP via email (and optionally via Twilio) for password reset.
    """
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Ensure a valid, active user exists
            try:
                user = SkillUser.objects.get(email=email, is_active=True)
            except SkillUser.DoesNotExist:
                messages.error(request, "No active user found with that email.")
                return redirect('accounts:forgot-password')

            # Generate OTP and store it in session
            otp = random.randint(100000, 999999)
            request.session['user_id'] = user.id
            request.session['otp'] = otp

            # Send OTP via email; pass OTP in context for email template
            form.save(
                request=request,
                email_template_name='users/password_reset_email.html',
                subject_template_name='users/password_reset_subject.txt',
                extra_email_context={'otp': otp}
            )

            # Optionally send OTP via Twilio if phone_number exists
            if user.phone_number:
                try:
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                        .verifications.create(to=user.phone_number, channel="sms")
                except TwilioRestException as e:
                    print(f"Twilio Error: {e}")
                    messages.warning(request,
                                     "Failed to send OTP via SMS. Please check your phone number or Twilio settings.")

            messages.success(request, 'An OTP has been sent to your email and phone (if provided).')
            return redirect('accounts:verify_otp_password')
    else:
        form = PasswordResetForm()

    return render(request, 'users/forgot_password.html', {'form': form})


def verify_otp_password(request):
    """
    Verifies OTP for password reset.
    If valid, stores a verified user in the session and redirects to the set new password page.
    """
    if request.method == 'POST':
        form = OTPFormPassword(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data.get('otp')
            session_otp = request.session.get('otp')
            user_id = request.session.get('user_id')

            if not user_id:
                messages.error(request, "Session expired. Please try again.")
                return redirect('accounts:forgot-password')

            user = get_object_or_404(SkillUser, id=user_id)
            valid = False

            # Check OTP sent via email
            if session_otp and str(otp_entered) == str(session_otp):
                valid = True
            else:
                # If email OTP doesn't match, try Twilio Verify if phone number exists
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
                # Mark the user as verified for password reset
                request.session['verified_user_id'] = user.id
                return redirect('accounts:set_new_password')
            else:
                messages.error(request, "Invalid OTP. Please try again.")
    else:
        form = OTPFormPassword()

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

                # Log in the user
                login(request, user)
                messages.success(request, "Your account has been activated!")

                # Redirect based on user role
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


User = get_user_model()


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
        context['total_active_instructors_with_payment'] = SkillUser.objects.filter(
            role='instructor',
            instructor_status='active',
            cartitem__payment_status='completed',
            cartitem__class_booking__isnull=True  # Filtering instructor fee payments
        ).distinct().count()
        context['total_learners'] = SkillUser.objects.filter(role='learner').count()

        # Class statistics
        context['total_classes'] = Class.objects.count()
        context['approved_classes'] = Class.objects.filter(is_approved=True).count()
        context['pending_classes'] = Class.objects.filter(is_approved=False).count()
        context['ongoing_classes'] = Class.objects.filter(status='ongoing', is_active=True).count()
        context['completed_classes'] = Class.objects.filter(status='completed').count()

        # Category statistics
        context['total_categories'] = SkillCategory.objects.count()
        context['categories_with_classes'] = SkillCategory.objects.filter(classes__isnull=False).distinct().count()

        # Enrollment statistics
        context['total_enrollments'] = Enrollment.objects.count()
        context['paid_enrollments'] = Enrollment.objects.filter(is_paid=True).count()
        context['booked_enrollments'] = Enrollment.objects.filter(is_booked=True).count()
        # Revenue Calculations
        context['class_revenue'] = CartItem.objects.filter(payment_status='completed').aggregate(Sum('amount'))[
                                       'amount__sum'] or 0
        context['instructor_payment_total'] = Order.objects.aggregate(Sum('total'))['total__sum'] or 0

        # Format revenue numbers
        context['class_revenue'] = localize(context['class_revenue'])
        context['instructor_payment_total'] = localize(context['instructor_payment_total'])
        # Revenue Breakdown
        class_revenue = \
            CartItem.objects.filter(payment_status='completed', class_booking__isnull=False).aggregate(Sum('amount'))[
                'amount__sum'] or 0
        instructor_fee_revenue = \
            CartItem.objects.filter(payment_status='completed', class_booking__isnull=True).aggregate(Sum('amount'))[
                'amount__sum'] or 0
        total_revenue = class_revenue + instructor_fee_revenue

        context['class_revenue'] = class_revenue
        context['instructor_fee_revenue'] = instructor_fee_revenue
        context['total_revenue'] = total_revenue

        # Order statistics
        context['total_orders'] = Order.objects.count()
        context['completed_orders'] = Order.objects.filter(total__gt=0).count()

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


def users_list(request):
    users = list(User.objects.all())
    for user in users:
        if user.role not in ['learner', 'instructor']:
            user.role = 'Admin'
    return render(request, 'users/users_list.html', {'users': users})


def instructors_list(request):
    instructors = User.objects.filter(role="instructor")
    # For each instructor, check if any notification has a non-null payment.
    for instructor in instructors:
        instructor.has_payments = Notification.objects.filter(user=instructor, payment__isnull=False).exists()
    return render(request, "users/instructors_list.html", {"instructors": instructors})


def learners_list(request):
    learners = User.objects.filter(role="learner")  # Assuming a `role` field exists
    return render(request, "users/learners_list.html", {"learners": learners})


def pending_classes(request):
    pending_class = Class.objects.filter(status="pending")  # Assuming a `status` field
    return render(request, "users/pending_classes.html", {"pending_classes": pending_class})


def class_list(request):
    classes = Class.objects.all()
    for class_instance in classes:
        class_instance.update_status()  # Ensure status is updated dynamically
    return render(request, "users/class_list.html", {"classes": classes})


def approved_classes(request):
    approved_class = Class.objects.filter(status="approved")
    return render(request, "users/approved_classes.html", {"approved_classes": approved_class})


def ongoing_classes(request):
    ongoing_class = Class.objects.filter(status="ongoing")
    return render(request, "users/ongoing_classes.html", {"ongoing_classes": ongoing_class})


def enrollment_list(request):
    # Show all enrollments if the user is staff; otherwise, only show enrollments for the current learner.
    if request.user.is_staff:
        enrollments = Enrollment.objects.all()
    else:
        enrollments = Enrollment.objects.filter(learner=request.user)
    return render(request, 'users/enrollment_list.html', {'enrollments': enrollments})


def paid_enrollments(request):
    # For staff, show all paid enrollments; for a learner, show only their paid enrollments.
    if request.user.is_staff:
        enrollments = Enrollment.objects.filter(is_paid=True)
    else:
        enrollments = Enrollment.objects.filter(is_paid=True, learner=request.user)
    return render(request, 'users/paid_enrollments.html', {'enrollments': enrollments})


def booked_enrollments(request):
    # Count pending payments in the cart for the current user
    pending_count = CartItem.objects.filter(user=request.user, payment_status='pending').count()

    # Fetch "booked" enrollments (using the is_booked field)
    if request.user.is_staff:
        enrollments = Enrollment.objects.filter(is_booked=True)
    else:
        enrollments = Enrollment.objects.filter(is_booked=True, learner=request.user)

    return render(request, 'users/booked_enrollments.html', {
        'enrollments': enrollments,
        'pending_count': pending_count
    })


@login_required
def order_list(request):
    # Get completed orders for the current user
    orders = Order.objects.filter(user=request.user, total__gt=0).order_by('-created_at')

    # Get pending cart items (unpaid items in cart)
    pending_cart_items = CartItem.objects.filter(user=request.user, payment_status='pending').order_by('-created_at')

    # Debugging Output (Optional)
    print(f"User: {request.user.username}")
    print(f"Total Completed Orders: {orders.count()}")
    print(f"Total Pending Cart Items: {pending_cart_items.count()}")

    for order in orders:
        print(f"Order {order.id} - Total: {order.total} - Status: {order.order_status}")

    context = {
        'orders': orders,
        'pending_cart_items': pending_cart_items,
    }
    return render(request, 'users/order_list.html', context)

def revenue_view(request):
    # Revenue from class purchases (filter only completed payments)
    class_revenue = CartItem.objects.filter(payment_status='completed', class_booking__isnull=False).aggregate(
        total=Sum('amount'))['total'] or 0

    # Revenue from instructor registration fees (filter orders where class_booking is null)
    instructor_fee_revenue = CartItem.objects.filter(payment_status='completed', class_booking__isnull=True).aggregate(
        total=Sum('amount'))['total'] or 0

    # Overall total revenue
    total_revenue = class_revenue + instructor_fee_revenue

    return render(request, 'users/revenue.html', {
        'class_revenue': f"{class_revenue:,.2f}",
        'instructor_fee_revenue': f"{instructor_fee_revenue:,.2f}",
        'total_revenue': f"{total_revenue:,.2f}"
    })


def feedback_list(request):
    feedbacks = Feedback.objects.all().order_by('-timestamp')  # Correct field name
    return render(request, 'users/feedback_list.html', {'feedbacks': feedbacks})
