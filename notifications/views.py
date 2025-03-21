from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from classes.models import Class
from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notification_list.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        # Retrieve all notifications for the current user in descending order.
        qs = Notification.objects.filter(user=self.request.user).order_by('-created_at')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        twenty_four_hours_ago = timezone.now() - timedelta(days=1)
        # Count notifications that are unread and created in the last 24 hours
        unread_count = Notification.objects.filter(
            user=self.request.user,
            read=False,
            created_at__gte=twenty_four_hours_ago
        ).count()
        context['unread_count'] = unread_count
        context['user_role'] = self.request.user.role
        return context


class NotificationDashboardView(TemplateView):
    template_name = "notifications_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # If the user is logged in, get their notifications and pass the role.
        if self.request.user.is_authenticated:
            notifications = Notification.objects.filter(user=self.request.user).order_by('-created_at')
            context['notifications'] = notifications
            context['user_role'] = self.request.user.role
        else:
            context['notifications'] = None

        # Get a sample of classes to display (for all users).
        # Optionally, you can filter these based on the user role.
        context['classes'] = Class.objects.all()[:6]
        return context
