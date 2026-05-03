from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Inventory
from datetime import timedelta

class Command(BaseCommand):
    help = "Mark inventory batches expiring within 48 hours as EXP and update surplus flags."
    
    def handle(self, *args, **options):
        today = timezone.localdate()
        cutoff = today + timedelta(hours=48)

        # Active batches expiring within the next 48 hours
        expired_qs = Inventory.objects.filter(
            status=Inventory.BatchStatus.ACTIVE,
            expiry_date__lte=cutoff,
        )

        count = expired_qs.count()

        # Mark them as expired
        expired_qs.update(status=Inventory.BatchStatus.EXPIRED)

        # Surplus batches that were active should also be marked surplus expired
        Inventory.objects.filter(
            expiry_date__lte=cutoff,
            surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE,
        ).update(surplus_status=Inventory.SurplusStatus.SURPLUS_EXPIRED)

        self.stdout.write(
            self.style.SUCCESS(f"Batches expiring within 48 hours marked as EXP: {count}")
        )
        