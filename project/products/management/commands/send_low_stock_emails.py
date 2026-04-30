from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from collections import defaultdict

from products.models import Product


class Command(BaseCommand):
    help = "Send daily low-stock email alerts to producers."

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent_count = 0
        skipped_count = 0

        # Group low-stock products by producer
        grouped = defaultdict(list)

        for product in Product.objects.select_related("producer"):
            total = product.computed_total_stock
            threshold = product.low_stock_threshold or 0
            producer = product.producer

            if not producer.email_low_stock_notifications:
                skipped_count += 1
                continue

            # Add to group if low and not already emailed
            if total <= threshold and not product.low_stock_email_sent:
                grouped[producer].append(product)

            # Reset flag when stock rises
            if total > threshold and product.low_stock_email_sent:
                product.low_stock_email_sent = False
                product.save(update_fields=["low_stock_email_sent"])

        # Send one email per producer
        for producer, products in grouped.items():
            context = {
                "producer_name": producer.farm_name,
                "products": products,
            }

            html_message = render_to_string(
                "emails/low_stock_alert.html",
                context
            )

            send_mail(
                subject="Low Stock Alert",
                message="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[producer.contact_email],
                html_message=html_message,
            )

            # Mark all included products as emailed
            for product in products:
                product.low_stock_email_sent = True
                product.save(update_fields=["low_stock_email_sent"])

            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Emails sent: {sent_count}, Producers skipped: {skipped_count}"
            )
        )