
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client


def send_sms(to, message):
    """
    Sends an SMS notification using Twilio.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to
        )
        return message.sid
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return None  # Return None if SMS sending fails


def send_notification(user, message):
    """
    Sends a notification via email and SMS.
    """
    # Send email notification
    try:
        send_mail(
            subject="Notification",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,  # Set to False for debugging, True for production
        )
    except Exception as e:
        print(f"Error sending email: {e}")

    # Send SMS if the user has a phone number
    if hasattr(user, "phone_number") and user.phone_number:  # Check if phone_number exists
        send_sms(user.phone_number, message)
