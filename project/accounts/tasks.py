from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

def send_welcome_email(user):
    subject = "Welcome to Our Bristol Regional Food Network"

    html_message = render_to_string("email/welcome_email.html", {
    "user": user,
    "year": timezone.now().year})
    plain_message = "Welcome to our Bristol Regional Food Network!"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    send_mail(subject, plain_message, from_email, [to], html_message=html_message)
