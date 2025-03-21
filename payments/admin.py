from django.contrib import admin
from .models import SiteConfiguration, CartItem, Order


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ['enable_payments', 'test_environment']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'class_booking', 'amount', 'payment_status']
    list_filter = ['payment_status']
    search_fields = ['user__username', 'class_booking__title']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'total', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username']
