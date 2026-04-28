# import dramatiq
# from django.core.mail import send_mail
# from django.template.loader import render_to_string
# from django.conf import settings
# from .models import Product
# from notifications.services.notifications import NotificationService

# @dramatiq.actor
# def check_low_stock():
#     for product in Product.objects.all():
#         total = product.computed_total_stock or 0
#         threshold = product.low_stock_threshold or 0
#         producer = product.producer

#         if total <= threshold:
#             # Create notification
#             NotificationService.create_unique(
#                 user=producer.user,
#                 type="PA",
#                 message=f"{product.name} is low on stock.",
#                 product=product
#             )

#             # Send email once
#             if not product.low_stock_email_sent:
#                 send_low_stock_email(product)
#                 product.low_stock_email_sent = True
#                 product.save()
#         else:
#             # Resolve any existing low-stock notifications
#             NotificationService.resolve_for_product(
#                 product,
#                 type="LOW_STOCK"
#             )

#             # Reset when stock rises above threshold
#             if product.low_stock_email_sent:
#                 product.low_stock_email_sent = False
#                 product.save()

# def send_low_stock_email(product):
#     producer = product.producer

#     # Respect producer preference
#     if not producer.email_low_stock_notifications:
#         return

#     subject = f"Low Stock Alert: {product.name}"

#     context = {
#         "producer_name": producer.farm_name,
#         "product": product,
#     }

#     html_message = render_to_string("emails/low_stock_alert.html", context)

#     send_mail(
#         subject,
#         "", # optional plain text
#         settings.DEFAULT_FROM_EMAIL,
#         [producer.contact_email],
#         html_message=html_message,
#     )