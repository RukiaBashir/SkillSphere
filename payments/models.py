from django.db import models
from classes.models import Class
from accounts.models import SkillUser


class SiteConfiguration(models.Model):
    enable_payments = models.BooleanField(default=False)
    test_environment = models.BooleanField(default=True)

    # add any other configuration fields as needed

    def __str__(self):
        return "Site Configuration"


class CartItem(models.Model):
    user = models.ForeignKey(SkillUser, on_delete=models.CASCADE)
    class_booking = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)  # Add this field

    def __str__(self):
        return f"{self.user.username} - {self.class_booking.title if self.class_booking else 'Registration Fee'}"


class Order(models.Model):
    user = models.ForeignKey(SkillUser, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add additional fields as needed (e.g., transaction id)
