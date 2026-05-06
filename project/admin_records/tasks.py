from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from products.models import Product
from notifications.models import Notification



def send_action_required_email(product_id, message):
    product = Product.objects.select_related("producer__user").get(id=product_id)
    producer = product.producer.user

    html_content = render_to_string(
        "admin_records/emails/action_required.html",
        {
            "producer_name": producer.name,
            "product_name": product.name,
            "message": message,
        }
    )

    email = EmailMultiAlternatives(
        subject=f"Action Required: {product.name}",
        body="Your email client does not support HTML emails.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[producer.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

    # Update product status → FLAGGED
    product.status = Product.Status.FLAGGED
    product.save()

    # Create in-app notification
    Notification.objects.create(
        user=producer,
        product=product,
        type=Notification.Type.PRODUCT_ALERT,
        message=f"Action Required: Your product '{product.name}' requires changes."
    )

def send_rejection_email(product_id, reason, admin_name):
    product = Product.objects.get(id=product_id)
    producer = product.producer.user

    html_content = render_to_string(
        "admin_records/emails/product_reject.html",
        {
            "producer_name": producer.name,
            "product_name": product.name,
            "reason": reason,
            "admin_name": admin_name,
        }
    )

    email = EmailMultiAlternatives(
        subject=f"Your product '{product.name}' has been rejected",
        body="Your email client does not support HTML emails.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[producer.email],
    )

    # THIS IS THE IMPORTANT PART
    email.attach_alternative(html_content, "text/html")

    email.send()