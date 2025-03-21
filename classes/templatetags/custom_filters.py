from django import template
from django.utils import timezone

from classes.models import Enrollment

register = template.Library()


@register.filter
def is_enrolled_by(class_obj, user):
    """
    Returns True if the given user is enrolled in the class.
    Assumes that the Class model has a reverse relationship named 'enrollments'
    and each enrollment has a 'learner' field.
    """
    # Adjust this logic if your Enrollment model uses a different reverse name.
    return class_obj.enrollments.filter(learner=user).exists()


@register.filter(name='subtract')
def subtract(value, arg):
    """
    Subtracts arg from value.
    Usage: {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''


@register.filter
def is_booked_by(class_obj, user):
    """
    Returns True if there is an Enrollment for the given class_obj and user
    where is_booked is True.
    """
    try:
        return Enrollment.objects.filter(class_obj=class_obj, learner=user, is_booked=True).exists()
    except Exception as e:
        # Optionally log the error, then return False
        return False


@register.filter
def has_started(schedule):
    """
    Returns True if the scheduled datetime is in the past (i.e. the class has started).
    """
    if not schedule:
        return False
    return timezone.now() >= schedule

