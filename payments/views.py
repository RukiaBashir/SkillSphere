import base64
import datetime
import json

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DeleteView

from accounts.models import SiteConfiguration
from classes.models import Enrollment
from notifications.models import Notification
from notifications.utils import send_sms
from .models import Class, CartItem


class MpesaPaymentView(LoginRequiredMixin, View):
    """
    Initiates an Mpesa STK push for a given class booking.
    Creates a CartItem with 'pending' status.
    If test mode is enabled in SiteConfiguration, bypass live processing.
    """

    def post(self, request, pk, *args, **kwargs):
        class_obj = get_object_or_404(Class, pk=pk)
        amount = class_obj.price

        # Create a CartItem for the purchase.
        cart_item = CartItem.objects.create(
            user=request.user,
            class_booking=class_obj,
            amount=amount,
            payment_status='pending'
        )

        # Check SiteConfiguration for test mode.
        config = SiteConfiguration.objects.first()
        if config and config.test_environment:
            # Test mode: bypass live processing.
            cart_item.payment_status = 'completed'
            cart_item.is_test_mode = True
            cart_item.transaction_id = f"TEST-{cart_item.id}"
            cart_item.processed_at = timezone.now()
            cart_item.save()
            notification_message = f"[Test Mode] Your payment for {class_obj.title} was processed successfully."
            Notification.objects.create(
                user=request.user,
                payment=cart_item,
                message=notification_message
            )
            return JsonResponse({
                "message": "Test mode: Payment processed successfully.",
                "response": {"test": True}
            })

        # --- Live Mpesa API Integration ---
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        token_url = settings.MPESA_TOKEN_URL

        token_response = requests.get(token_url, auth=(consumer_key, consumer_secret))
        try:
            token_data = token_response.json()
        except json.decoder.JSONDecodeError:
            return JsonResponse({
                "error": "Failed to decode token response",
                "response": token_response.text
            }, status=500)

        access_token = token_data.get("access_token")
        if not access_token:
            return JsonResponse({
                "error": "No access token found in token response",
                "response": token_data
            }, status=500)

        business_short_code = settings.MPESA_BUSINESS_SHORT_CODE
        passkey = settings.MPESA_PASSKEY
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = business_short_code + passkey + timestamp
        password = base64.b64encode(data_to_encode.encode()).decode('utf-8')

        stk_push_url = settings.MPESA_STK_PUSH_URL
        callback_url = settings.MPESA_CALLBACK_URL

        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(amount),
            "PartyA": request.user.phone_number,
            "PartyB": business_short_code,
            "PhoneNumber": request.user.phone_number,
            "CallBackURL": callback_url,
            "AccountReference": f"Class-{class_obj.pk}",
            "TransactionDesc": f"Payment for {class_obj.title}"
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(stk_push_url, json=payload, headers=headers)
        try:
            response_data = response.json()
        except json.decoder.JSONDecodeError:
            return JsonResponse({
                "error": "Failed to decode STK push response",
                "response": response.text
            }, status=500)

        if response.status_code == 200:
            return JsonResponse({"message": "Mpesa payment initiated", "response": response_data})
        else:
            return JsonResponse({"error": "Failed to initiate Mpesa payment", "response": response.text}, status=400)


def mpesa_callback(request):
    """
    Processes the Mpesa callback.
    If the payment is successful, updates the CartItem to 'completed'
    and creates a Notification referencing the payment.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    try:
        # Attempt to parse the JSON body
        callback_data = json.loads(request.body)
        print("Mpesa callback received:", callback_data)

        # Navigate through the callback JSON structure
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        callback_metadata = stk_callback.get("CallbackMetadata", {})

        # Initialize variables
        amount = None
        mpesa_receipt_number = None
        phone_number = None

        # Extract values from CallbackMetadata items if available
        items = callback_metadata.get("Item", [])
        if items:
            if len(items) >= 2:
                amount = items[0].get("Value")
                mpesa_receipt_number = items[1].get("Value")
            if len(items) >= 4:
                phone_number = items[3].get("Value")

        # Retrieve the CartItem using checkout_request_id (ensure your CartItem model has this field)
        payment = CartItem.objects.filter(checkout_request_id=checkout_request_id).first()

        if payment:
            if result_code == 0:
                # Payment successful: update CartItem status and record details
                payment.payment_status = "completed"
                payment.mpesa_receipt_number = mpesa_receipt_number
                payment.amount_paid = amount
                payment.save()

                notification_message = f"Your M-Pesa payment of {amount} KES was successful. Receipt: {mpesa_receipt_number}"
                # Create a notification referencing the payment
                Notification.objects.create(
                    user=payment.user,
                    payment=payment,
                    message=notification_message
                )
                if phone_number:
                    send_sms(phone_number, notification_message)
            else:
                # Payment failed: update status and create a notification with the error message
                payment.payment_status = "failed"
                payment.mpesa_error_code = result_code
                payment.mpesa_error_message = result_desc
                payment.save()

                notification_message = f"Your M-Pesa payment failed. Error: {result_desc}"
                Notification.objects.create(
                    user=payment.user,
                    payment=payment,
                    message=notification_message
                )
                if phone_number:
                    send_sms(phone_number, notification_message)

        return JsonResponse({"status": "Processed"})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


class CartListView(LoginRequiredMixin, ListView):
    """
    Lists all pending CartItems for the current user.
    For learners, these represent class bookings not yet paid.
    """
    model = CartItem
    template_name = 'cart_list.html'
    context_object_name = 'cart_items'

    def get_queryset(self):
        item_pk = self.request.GET.get('item')
        if item_pk:
            try:
                class_obj = Class.objects.get(pk=item_pk)
                # Get all cart items for this user and class
                cart_items_for_item = CartItem.objects.filter(user=self.request.user, class_booking=class_obj)
                if cart_items_for_item.count() > 1:
                    # If there are duplicates, keep the first and delete the rest
                    first_item = cart_items_for_item.first()
                    cart_items_for_item.exclude(pk=first_item.pk).delete()
                elif not cart_items_for_item.exists():
                    CartItem.objects.create(
                        user=self.request.user,
                        class_booking=class_obj,
                        amount=class_obj.price,
                        payment_status='pending'
                    )
            except Class.DoesNotExist:
                pass
        return CartItem.objects.filter(user=self.request.user, payment_status='pending')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_orders_count'] = self.get_queryset().count()
        return context


class CartDeleteView(LoginRequiredMixin, DeleteView):
    """
    Deletes a pending CartItem for the current user.
    """
    model = CartItem
    success_url = reverse_lazy('payments:cart-list')

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user, payment_status='pending')

    def get(self, request, *args, **kwargs):
        return redirect(self.success_url)


class CheckoutView(LoginRequiredMixin, View):
    """
    Displays the checkout page and processes payment for pending CartItems.
    Upon payment confirmation (via admin/test/live processing), marks CartItems
    as completed, creates an Order, and for class purchases, creates/updates
    Enrollment records so that booking details become visible.
    """

    def get(self, request, *args, **kwargs):
        cart_items = CartItem.objects.filter(user=request.user, payment_status='pending')
        total = sum(item.amount for item in cart_items)
        return render(request, 'checkout.html', {'cart_items': cart_items, 'total': total})

    def post(self, request, *args, **kwargs):
        cart_items = CartItem.objects.filter(user=request.user, payment_status='pending')
        if not cart_items.exists():
            return redirect('payments:cart-list')

        total = sum(item.amount for item in cart_items)
        config = SiteConfiguration.objects.first()  # Admin site configuration

        # Admin bypass: if payments are disabled.
        if not config or not config.enable_payments:
            for payment in cart_items:
                payment.payment_status = 'completed'
                # Mark as test mode for logging purposes
                payment.is_test_mode = True
                payment.transaction_id = f"TEST-{payment.id}"
                payment.processed_at = timezone.now()
                payment.save()
                class_title = payment.class_booking.title if payment.class_booking else "Registration Fee"
                Notification.objects.create(
                    user=payment.user,
                    payment=payment,
                    message=f"[Admin Bypass] Your payment for {class_title} was processed successfully."
                )
                # For class purchases, create/update Enrollment
                if payment.class_booking:
                    enrollment, created = Enrollment.objects.get_or_create(
                        learner=payment.user,
                        class_obj=payment.class_booking,
                        defaults={'is_paid': True, 'paid_at': timezone.now()}
                    )
                    if not created:
                        enrollment.is_paid = True
                        enrollment.paid_at = timezone.now()
                        enrollment.save()
            return JsonResponse({
                "message": "Payments bypassed via admin configuration. Payment processed successfully.",
                "total": total
            })

        # Test mode: auto-complete payments.
        if config and config.test_environment:
            for payment in cart_items:
                payment.payment_status = 'completed'
                payment.is_test_mode = True
                payment.transaction_id = f"TEST-{payment.id}"
                payment.processed_at = timezone.now()
                payment.save()
                class_title = payment.class_booking.title if payment.class_booking else "Registration Fee"
                Notification.objects.create(
                    user=payment.user,
                    payment=payment,
                    message=f"[Test Mode] Your payment for {class_title} was processed successfully."
                )
                # Create/update Enrollment if a class was purchased
                if payment.class_booking:
                    enrollment, created = Enrollment.objects.get_or_create(
                        learner=payment.user,
                        class_obj=payment.class_booking,
                        defaults={'is_paid': True, 'paid_at': timezone.now()}
                    )
                    if not created:
                        enrollment.is_paid = True
                        enrollment.paid_at = timezone.now()
                        enrollment.save()
            return JsonResponse({
                "message": "Test Environment: Payment processed successfully.",
                "total": total
            })

        # Live Payment Processing via Mpesa.
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        token_url = settings.MPESA_TOKEN_URL

        try:
            token_response = requests.get(token_url, auth=(consumer_key, consumer_secret))
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")

            business_short_code = settings.MPESA_BUSINESS_SHORT_CODE
            passkey = settings.MPESA_PASSKEY
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            data_to_encode = f"{business_short_code}{passkey}{timestamp}"
            password = base64.b64encode(data_to_encode.encode()).decode('utf-8')

            stk_push_url = settings.MPESA_STK_PUSH_URL
            callback_url = settings.MPESA_CALLBACK_URL

            payload = {
                "BusinessShortCode": business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": str(total),
                "PartyA": int("254" + request.user.phone_number[1:]),
                "PartyB": business_short_code,
                "PhoneNumber": int("254" + request.user.phone_number[1:]),
                "CallBackURL": callback_url,
                "AccountReference": f"Checkout-{request.user.id}",
                "TransactionDesc": "Payment for cart checkout"
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(stk_push_url, json=payload, headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                for payment in cart_items:
                    payment.payment_status = 'completed'
                    payment.processed_at = timezone.now()
                    payment.save()
                    class_title = payment.class_booking.title if payment.class_booking else "Registration Fee"
                    Notification.objects.create(
                        user=payment.user,
                        payment=payment,
                        message=f"Your payment for {class_title} has been completed successfully."
                    )
                    # Create/update Enrollment for purchased classes
                    if payment.class_booking:
                        enrollment, created = Enrollment.objects.get_or_create(
                            learner=request.user,
                            class_obj=payment.class_booking,
                            defaults={'is_paid': True, 'paid_at': timezone.now()}
                        )
                        if not created:
                            enrollment.is_paid = True
                            enrollment.paid_at = timezone.now()
                            enrollment.save()
                return JsonResponse({
                    "message": "Mpesa payment initiated and payments completed",
                    "response": response.json()
                })
            else:
                return JsonResponse({
                    "error": "Failed to initiate Mpesa payment",
                    "response": response.text
                }, status=400)
        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"Request failed: {e}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {e}"}, status=500)

class AddToCartView(LoginRequiredMixin, View):
    """
    Handles adding a class to the cart.
    In a test environment (SiteConfiguration.test_environment=True),
    the CartItem is immediately marked as "completed" so that the class appears as purchased.
    """

    def post(self, request, pk=None, *args, **kwargs):
        # Retrieve site configuration; if not found, assume production defaults.
        site_config = SiteConfiguration.objects.first()
        is_test = site_config.test_environment if site_config else False

        # Case for instructor registration fee (when no pk is provided)
        if pk is None:
            fee_amount = getattr(settings, "INSTRUCTOR_REGISTRATION_FEE", 100.00)
            cart_item = CartItem.objects.filter(user=request.user, class_booking__isnull=True).first()
            if not cart_item:
                cart_item = CartItem.objects.create(
                    user=request.user,
                    class_booking=None,
                    amount=fee_amount,
                    payment_status='pending'
                )
            if is_test:
                cart_item.payment_status = "completed"
                cart_item.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                updated_cart_count = CartItem.objects.filter(user=request.user, payment_status='pending').count()
                return JsonResponse({
                    "success": True,
                    "message": "Instructor registration fee added to cart",
                    "pending_orders_count": updated_cart_count
                })
            return redirect('payments:cart-list')

        # Process a class purchase.
        try:
            class_obj = Class.objects.get(pk=pk)
        except Class.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": False, "message": "Class not found."}, status=404)
            messages.error(request, "Class not found.")
            return redirect('classes:class-list')

        cart_item = CartItem.objects.filter(user=request.user, class_booking=class_obj).first()
        if cart_item:
            if cart_item.payment_status == 'completed':
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        "success": True,
                        "message": "Class already purchased. Please join the class.",
                        "already_purchased": True
                    })
                messages.info(request, "You have already purchased this class. Please join the class.")
                return redirect('classes:class-detail', pk=class_obj.pk)
        else:
            cart_item = CartItem.objects.create(
                user=request.user,
                class_booking=class_obj,
                amount=class_obj.price,
                payment_status='pending'
            )

        # In test mode, mark the item as completed immediately.
        if is_test:
            cart_item.payment_status = "completed"
            cart_item.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            updated_cart_count = CartItem.objects.filter(user=request.user, payment_status='pending').count()
            return JsonResponse({
                "success": True,
                "message": "Item added to cart",
                "pending_orders_count": updated_cart_count
            })
        return redirect('payments:cart-list')


class CartItemHistoryListView(LoginRequiredMixin, ListView):
    """
    Displays payment history.
    For instructors, shows registration fee payments (with class_booking null).
    For learners, shows completed payments for class bookings.
    """
    model = CartItem
    template_name = 'history.html'
    context_object_name = 'payment_history'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'instructor':
            return CartItem.objects.filter(user=user, class_booking__isnull=True)
        else:
            return CartItem.objects.filter(user=user, payment_status='completed', class_booking__isnull=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        history = []

        if user.role == 'instructor':
            for payment in self.get_queryset():
                activation_date = payment.created_at
                expiry_date = activation_date + datetime.timedelta(days=365)
                history.append({
                    'payment': payment,
                    'activation_date': activation_date,
                    'expiry_date': expiry_date,
                    'status': getattr(user, 'instructor_status', 'N/A'),  # For example: active/inactive
                })
        else:
            for payment in self.get_queryset():
                purchase_date = payment.created_at
                expiry_date = purchase_date + datetime.timedelta(days=365)
                is_expired = now > expiry_date
                history.append({
                    'payment': payment,
                    'purchase_date': purchase_date,
                    'expiry_date': expiry_date,
                    'is_expired': is_expired,
                    'join_url': payment.class_booking.get_classroom_url()
                                if payment.class_booking and hasattr(payment.class_booking, 'get_classroom_url')
                                else None,
                })
        context['payment_history'] = history
        return context

class PaymentHistoryListView(LoginRequiredMixin, ListView):
    """
    Displays payment history.
    - For instructors: shows completed registration fee payments (with class_booking null).
    - For learners: shows all completed CartItem records (i.e. purchased classes).
    Also adds extra context for learners: purchase date, expiry date, is_expired flag, join URL,
    and a list of purchased class IDs.
    """
    model = CartItem
    template_name = 'history.html'
    context_object_name = 'payment_history'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'instructor':
            # Registration fee payments only (no associated class) that are completed.
            return CartItem.objects.filter(user=user, class_booking__isnull=True, payment_status='completed')
        else:
            # For learners, return all completed CartItem records.
            return CartItem.objects.filter(user=user, payment_status='completed')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        history = []
        purchased_class_ids = []  # For learners: list of purchased class IDs

        if user.role == 'instructor':
            for cart_item in self.get_queryset():
                activation_date = cart_item.created_at
                expiry_date = activation_date + datetime.timedelta(days=365)
                history.append({
                    'cart_item': cart_item,
                    'activation_date': activation_date,
                    'expiry_date': expiry_date,
                    'status': getattr(user, 'instructor_status', 'N/A'),
                })
        else:
            for cart_item in self.get_queryset():
                purchase_date = cart_item.created_at
                expiry_date = purchase_date + datetime.timedelta(days=365)
                is_expired = now > expiry_date
                history.append({
                    'cart_item': cart_item,
                    'purchase_date': purchase_date,
                    'expiry_date': expiry_date,
                    'is_expired': is_expired,
                    'join_url': (cart_item.class_booking.get_classroom_url()
                                 if cart_item.class_booking and hasattr(cart_item.class_booking, 'get_classroom_url')
                                 else None),
                })
                if cart_item.class_booking:
                    purchased_class_ids.append(cart_item.class_booking.id)
        context['payment_history'] = history
        context['purchased_class_ids'] = purchased_class_ids
        return context