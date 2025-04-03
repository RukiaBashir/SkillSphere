from django.urls import path
from . import views
from .views import PaymentStatusView

app_name = 'payments'

urlpatterns = [
    # Initiate an Mpesa STK push payment for a class booking
    path('mpesa/<int:pk>/', views.MpesaPaymentView.as_view(), name='mpesa-payment'),
    # Display the current user's cart (pending payments)
    path('add-to-cart/<int:pk>/', views.AddToCartView.as_view(), name='add-to-cart'),
    path('cart/', views.CartListView.as_view(), name='cart-list'),
    # Remove a pending Payment item from the cart
    path('cart-delete/<int:pk>/', views.CartDeleteView.as_view(), name='cart-delete'),
    # Checkout view to process payment for items in the cart
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('payment-status/', PaymentStatusView.as_view(), name='payment_status'),
    # Add a class to the cart (or instructor registration fee if pk is None)
    path('add-to-cart/<int:pk>/', views.AddToCartView.as_view(), name='add-to-cart'),
    # View payment history (for learners and instructors)
    path('payment-history/', views.PaymentHistoryListView.as_view(), name='payment-history'),
]
