import base64
import datetime
import json

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DeleteView
from django.views.generic import TemplateView

from accounts.models import SiteConfiguration
from classes.models import Enrollment, Class
from notifications.models import Notification
from notifications.utils import send_sms
from .models import CartItem, Order


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

        config = SiteConfiguration.objects.first()
        # If in test mode, bypass live processing.
        if config and config.test_environment:
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
        callback_data = json.loads(request.body)
        print("Mpesa callback received:", callback_data)

        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        callback_metadata = stk_callback.get("CallbackMetadata", {})

        amount = None
        mpesa_receipt_number = None
        phone_number = None

        items = callback_metadata.get("Item", [])
        if items:
            if len(items) >= 2:
                amount = items[0].get("Value")
                mpesa_receipt_number = items[1].get("Value")
            if len(items) >= 4:
                phone_number = items[3].get("Value")

        payment = CartItem.objects.filter(checkout_request_id=checkout_request_id).first()

        if payment:
            if result_code == 0:
                payment.payment_status = "completed"
                payment.mpesa_receipt_number = mpesa_receipt_number
                payment.amount_paid = amount
                payment.save()

                notification_message = f"Your M-Pesa payment of {amount} KES was successful. Receipt: {mpesa_receipt_number}"
                Notification.objects.create(
                    user=payment.user,
                    payment=payment,
                    message=notification_message
                )
                if phone_number:
                    send_sms(phone_number, notification_message)
            else:
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


class PaymentStatusView(LoginRequiredMixin, TemplateView):
    template_name = "mpesa_callback.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Retrieve payment status details from session and remove them so they're not reused.
        payment_status = self.request.session.pop('payment_status', {})
        context.update(payment_status)
        return context


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
                cart_items_for_item = CartItem.objects.filter(user=self.request.user, class_booking=class_obj)
                if cart_items_for_item.count() > 1:
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
            Order.objects.create(user=request.user, total=total)
            request.session['payment_status'] = {
                'result_code': 0,
                'amount': float(total),
                'mpesa_receipt_number': f"TEST-{total}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                'phone_number': request.user.phone_number,
                'result_desc': "Payment processed via admin bypass.",
                'merchant_request_id': "",
                'checkout_request_id': ""
            }
            return redirect('payments:payment_status')

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
            Order.objects.create(user=request.user, total=total)
            request.session['payment_status'] = {
                'result_code': 0,
                'amount': float(total),
                'mpesa_receipt_number': f"TEST-{total}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                'phone_number': request.user.phone_number,
                'result_desc': "Payment processed in test mode.",
                'merchant_request_id': "",
                'checkout_request_id': ""
            }
            return redirect('payments:payment_status')

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
                Order.objects.create(user=request.user, total=total)
                response_data = response.json()
                request.session['payment_status'] = {
                    'result_code': 0,
                    'amount': float(total),
                    'mpesa_receipt_number': response_data.get("MpesaReceiptNumber", ""),
                    'phone_number': request.user.phone_number,
                    'result_desc': response_data.get("ResponseDescription", "Payment initiated"),
                    'merchant_request_id': response_data.get("MerchantRequestID", ""),
                    'checkout_request_id': response_data.get("CheckoutRequestID", "")
                }
                return redirect('payments:payment_status')
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
        site_config = SiteConfiguration.objects.first()
        is_test = site_config.test_environment if site_config else False

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
    template_name = 'payment_history.html'
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
        current_time = timezone.now()
        history = []

        if user.role == 'instructor':
            for payment in self.get_queryset():
                activation_date = payment.created_at
                expiry_date = activation_date + datetime.timedelta(days=365)
                history.append({
                    'payment': payment,
                    'activation_date': activation_date,
                    'expiry_date': expiry_date,
                    'status': getattr(user, 'instructor_status', 'N/A'),
                })
        else:
            for payment in self.get_queryset():
                purchase_date = payment.created_at
                expiry_date = purchase_date + datetime.timedelta(days=365)
                is_expired = current_time > expiry_date
                history.append({
                    'payment': payment,
                    'purchase_date': purchase_date,
                    'expiry_date': expiry_date,
                    'is_expired': is_expired,
                    'join_url': payment.class_booking.get_classroom_url() if payment.class_booking and hasattr(
                        payment.class_booking, 'get_classroom_url') else None,
                })
        context['payment_history'] = history
        return context


class PaymentHistoryListView(LoginRequiredMixin, ListView):
    model = CartItem
    template_name = 'payment_history.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).order_by('-created_at')
