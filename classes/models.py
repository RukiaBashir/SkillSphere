from django.db import models
from django.utils import timezone
from django.utils.timezone import now

from accounts.models import SkillUser
import time


class SkillCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(SkillUser, on_delete=models.CASCADE, related_name='skill_categories')

    def __str__(self):
        return self.name

    def has_classes(self):
        # This method checks if there are any related Class objects.
        # Make sure your related Class model defines:
        # category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name='classes')
        return self.classes.exists()


class Class(models.Model):
    STATUS_CHOICES = [
        ('coming_soon', 'Coming Soon'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    local_image = models.ImageField(upload_to='classes/', blank=True, null=True)  # Local uploads
    external_image_url = models.URLField(blank=True, null=True)  # Supabase or CDN
    schedule = models.DateTimeField()
    venue_address = models.CharField(max_length=255, blank=True, null=True)
    instructor = models.ForeignKey(SkillUser, on_delete=models.CASCADE, limit_choices_to={'role': 'instructor'})
    category = models.ForeignKey(SkillCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='classes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='coming_soon')
    is_approved = models.BooleanField(default=False)  # For pending course approvals
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def update_status(self):
        """Update status based on the schedule and is_active."""
        if self.schedule > now():
            self.status = 'coming_soon'
        elif self.schedule <= now() and self.is_active:
            self.status = 'ongoing'
        else:
            self.status = 'completed'
        self.save(update_fields=['status'])

    @property
    def get_image_url(self):
        if self.external_image_url:
            return self.external_image_url
        elif self.local_image:
            return self.local_image.url
        return None


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
    progress = models.PositiveIntegerField(default=0)

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
