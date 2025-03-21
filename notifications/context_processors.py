# core/context_processors.py
from django.utils import timezone
from datetime import timedelta

from notifications.models import Notification
from payments.models import CartItem


def notification_and_payment_counts(request):
    if request.user.is_authenticated:
        twenty_four_hours_ago = timezone.now() - timedelta(days=1)
        notification_count = Notification.objects.filter(
            user=request.user,
            read=False,
            created_at__gte=twenty_four_hours_ago
        ).count()
        pending_orders_count = CartItem.objects.filter(
            user=request.user,
            payment_status='pending'
        ).count()
    else:
        notification_count = 0
        pending_orders_count = 0
    return {
        'notification_count': notification_count,
        'pending_orders_count': pending_orders_count,
    }
