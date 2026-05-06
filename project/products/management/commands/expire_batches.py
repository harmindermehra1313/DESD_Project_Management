from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Inventory, InventoryUpdateHistory
from datetime import timedelta, datetime, time
from django.utils.timezone import make_aware

from project.products.views import batch

class Command(BaseCommand):
    help = "Mark inventory batches expiring within 48 hours as EXP and update surplus flags."

    def handle(self, *args, **options):
        today = timezone.localdate()
        cutoff = today + timedelta(hours=48)

        # Active batches expiring within 48 hours
        expiring_batches = Inventory.objects.filter(
            # status=Inventory.BatchStatus.ACTIVE,
            expiry_date__lte=cutoff,
        )

        count = 0

        for batch in expiring_batches:
            # If the batch has an active reduction, log that it ended due to expiry
            if batch.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE:
                InventoryUpdateHistory.objects.create(
                    inventory=batch,
                    user=None, # system action
                    event_type="reduction_ended",
                    snapshot_discount=batch.surplus_discount_percentage,
                    snapshot_expiry=batch.surplus_expiry,
                    snapshot_note=batch.surplus_note,
                    ended_reason="expired",
                )

                # Mark surplus as expired
                batch.surplus_status = Inventory.SurplusStatus.SURPLUS_EXPIRED
                batch.surplus_discount_percentage = None
                batch.surplus_expiry = None
                batch.surplus_note = None

            # Mark the batch itself as expired if not deleted
            if batch.status != Inventory.BatchStatus.DELETED:
                batch.status = Inventory.BatchStatus.EXPIRED

            batch.save()

            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Batches expiring within 48 hours marked as EXP: {count}"
            )
        )
