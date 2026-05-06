from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from products.models import Inventory

class Command(BaseCommand):
    help = "Send daily alerts to producers for batches expiring in 72 hours."

    def handle(self, *args, **options):
        target_date = timezone.localdate() + timedelta(days=3)
        sent_count = 0

        # Find active inventory expiring exactly 3 days from now
        expiring_batches = Inventory.objects.filter(
            status=Inventory.BatchStatus.ACTIVE,
            expiry_date=target_date
        ).select_related("product", "product__producer")

        # Group by producer
        grouped = defaultdict(list)
        for batch in expiring_batches:
            grouped[batch.product.producer].append(batch)

        # Send one email per producer
        for producer, batches in grouped.items():
            message_lines = [f"Hello {producer.farm_name},\n", "The following batches will expire in 72 hours:\n"]
            for b in batches:
                message_lines.append(f"- {b.product.name} (Batch added: {b.harvest_date}): {b.remaining_quantity} {b.product.get_unit_display()} remaining.")
            
            message_lines.append("\nPlease review your inventory.\n\n— Your BRFN Dashboard")
            
            send_mail(
                subject="Alert: Batches Expiring in 72 Hours",
                message="\n".join(message_lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[producer.contact_email],
                fail_silently=False,
            )
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Expiry emails sent to {sent_count} producers."))