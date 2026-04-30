from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Inventory


class Command(BaseCommand):
    help = "Mark expired inventory batches as EXP and update surplus flags."

    def handle(self, *args, **options):
        today = timezone.localdate()

        # Active batches that have passed expiry date
        expired_qs = Inventory.objects.filter(
            status=Inventory.BatchStatus.ACTIVE,
            expiry_date__lt=today,
        )

        count = expired_qs.count()

        # Mark them as expired
        expired_qs.update(status=Inventory.BatchStatus.EXPIRED)

        # Surplus batches that were active should also be marked surplus-expired
        Inventory.objects.filter(
            expiry_date__lt=today,
            surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE,
        ).update(surplus_status=Inventory.SurplusStatus.SURPLUS_EXPIRED)

        self.stdout.write(
            self.style.SUCCESS(f"Expired batches marked as EXP: {count}")
        )
        