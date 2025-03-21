from django.urls import path
from .views import NotificationListView, NotificationDashboardView

app_name = 'notification'

urlpatterns = [
    # List all notifications for the current user
    path('list/', NotificationListView.as_view(), name='notification-list'),

    # Display the notifications dashboard (with sample classes and user role)
    path('dashboard/', NotificationDashboardView.as_view(), name='notification-dashboard'),
]