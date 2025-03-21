from django.db import models
from django.utils import timezone

from accounts.models import SkillUser


class SkillCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Class(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='classes/', blank=True, null=True)
    schedule = models.DateTimeField()
    venue_address = models.CharField(max_length=255, blank=True, null=True)
    instructor = models.ForeignKey(SkillUser, on_delete=models.CASCADE, limit_choices_to={'role': 'instructor'})
    category = models.ForeignKey(SkillCategory, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    BEGINNER = 'Beginner'
    INTERMEDIATE = 'Intermediate'
    EXPERT = 'Expert'
    LEARNING_STAGE_CHOICES = [
        (BEGINNER, 'Beginner'),
        (INTERMEDIATE, 'Intermediate'),
        (EXPERT, 'Expert'),
    ]

    class_obj = models.ForeignKey(
        Class,
        related_name='enrollments',
        on_delete=models.CASCADE
    )
    learner = models.ForeignKey(
        SkillUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'learner'},
        related_name='enrollments'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    is_booked = models.BooleanField(default=False)
    booked_at = models.DateTimeField(null=True, blank=True)

    # New field for learning progress
    learning_stage = models.CharField(
        max_length=20,
        choices=LEARNING_STAGE_CHOICES,
        default=BEGINNER
    )

    def mark_paid(self):
        self.is_paid = True
        self.paid_at = timezone.now()
        self.save()

    def mark_booked(self):
        self.is_booked = True
        self.booked_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.learner} enrolled in {self.class_obj} ({self.learning_stage})"
