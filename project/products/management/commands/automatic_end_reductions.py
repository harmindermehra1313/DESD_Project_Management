from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Inventory, InventoryUpdateHistory

class Command(BaseCommand):
    help = "Automatically end surplus reductions whose expiry time has passed."

    def handle(self, *args, **options):
        now = timezone.now()

        # Active reductions whose deal expiry has passed
        expired_deals = Inventory.objects.filter(
            surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE,
            surplus_expiry__lte=now,
        )

        count = expired_deals.count()

        for batch in expired_deals:
            # Log the reduction ending
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=None,
                event_type="reduction_ended",
                snapshot_discount=batch.surplus_discount_percentage,
                snapshot_expiry=batch.surplus_expiry,
                snapshot_note=batch.surplus_note,
                ended_reason="expired",
            )

            # Reset surplus fields
            batch.surplus_status = Inventory.SurplusStatus.SURPLUS_EXPIRED
            batch.surplus_discount_percentage = None
            batch.surplus_expiry = None
            batch.surplus_note = None

            batch.save(update_fields=[
                "surplus_status",
                "surplus_discount_percentage",
                "surplus_expiry",
                "surplus_note",
            ])

        self.stdout.write(
            self.style.SUCCESS(
                f"Automatically ended {count} surplus reductions whose expiry has passed."
            )
        )
