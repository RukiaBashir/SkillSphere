from django.db import models

from accounts.models import SkillUser
from payments.models import CartItem


class Notification(models.Model):
    user = models.ForeignKey(SkillUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    payment = models.ForeignKey(
        CartItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications'
    )

    def __str__(self):
        return f"Notification for {self.user.username}"
