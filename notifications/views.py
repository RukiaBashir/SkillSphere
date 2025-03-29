from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.generic import ListView, TemplateView

from classes.models import Class
from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notification_list.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).order_by('-created_at')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(days=1)
        unread_count = Notification.objects.filter(
            user=self.request.user,
            read=False,
            created_at__gte=twenty_four_hours_ago
        ).count()
        context['unread_count'] = unread_count
        context['user_role'] = self.request.user.role

        # Add a time_label for each notification:
        for notification in context['notifications']:
            if notification.created_at < twenty_four_hours_ago:
                # timesince returns a string like "2 days, 3 hours"
                notification.time_label = timesince(notification.created_at, now)
            else:
                notification.time_label = "New"
        return context


class NotificationDashboardView(TemplateView):
    template_name = "notifications_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(days=1)
        if self.request.user.is_authenticated:
            notifications = Notification.objects.filter(user=self.request.user).order_by('-created_at')
            # Add a time_label for each notification
            for notification in notifications:
                if notification.created_at < twenty_four_hours_ago:
                    notification.time_label = timesince(notification.created_at, now)
                else:
                    notification.time_label = "New"
            context['notifications'] = notifications
            context['user_role'] = self.request.user.role
        else:
            context['notifications'] = None

        # Get a sample of classes to display (for all users).
        context['classes'] = Class.objects.all()[:6]
        return context