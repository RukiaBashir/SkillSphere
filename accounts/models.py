from django.conf.urls.static import static
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class SiteConfiguration(models.Model):
    test_environment = models.BooleanField(
        default=False,
        help_text="Enable this to bypass live payment processing during checkout."
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Site Configuration"


class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)


class SkillUser(AbstractUser):
    ROLE_CHOICES = [
        ('learner', 'Learner'),
        ('instructor', 'Instructor'),
    ]
    INSTRUCTOR_STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
    ]

    instructor_status = models.CharField(
        max_length=10,
        choices=INSTRUCTOR_STATUS_CHOICES,
        default='inactive'
    )

    # Fields from the form
    username = models.CharField(max_length=10, unique=True)
    email = models.EmailField(unique=False)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    specialization = models.CharField(max_length=100)
    birth_date = models.DateField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    local_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    external_image_url = models.URLField(blank=True, null=True)
   

    # Use the custom user manager
    objects = CustomUserManager()

    # User model customizations
    USERNAME_FIELD = 'username'  # Username is the primary identifier
    REQUIRED_FIELDS = ['email']  # Email is required, and others can be added if needed

    def __str__(self):
        return self.username

    def get_absolute_url(self):
        return reverse('user_profile', kwargs={'pk': self.pk})  # Example URL, adjust as needed
    @property
    def profile_image_url(self):
        """Return whichever image is available: local first, then external, else default."""
        if self.local_image:
            return self.local_image.url
        elif self.external_image_url:
            return self.external_image_url
        return static('img/avatars/user.png')  # Fallback image path in static folder


class ContactQuerySet(models.query.QuerySet):

    def search(self, query):
        lookups = (Q(title__icontains=query) |
                   Q(date__icontains=query)
                   )
        return self.filter(lookups).distinct()


class FeedbackManager(models.Manager):
    def get_queryset(self):
        return ContactQuerySet(self.model, using=self._db)

    def all(self):
        return self.get_queryset()

    def get_by_id(self, pk):
        qs = self.get_queryset().filter(id=pk)
        if qs.count() == 1:
            return qs.first()
        return None

    def search(self, query):
        return self.get_queryset().search(query)


class Feedback(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    f_name = models.CharField(max_length=255, )
    f_message = models.TextField(max_length=2255, )
    f_email = models.EmailField(max_length=255, unique=False)
    f_reply = models.TextField(max_length=2255, unique=False, default='Hi Friend, Thank you For you feedback!!!')

    objects = FeedbackManager()

    class Meta:
        verbose_name_plural = 'Feedbacks'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.f_name} - {self.f_email}"
