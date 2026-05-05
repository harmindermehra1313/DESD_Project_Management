from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time, datetime
from django.utils.timezone import make_aware
from products.models import Inventory, InventoryUpdateHistory

class Command(BaseCommand):
    help = "Automatically apply 50% surplus reductions to batches expiring within 96 hours."

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now + timedelta(hours=96)

        # Find batches that:
        # - are active
        # - have no existing surplus reduction
        # - expire within 96 hours
        batches = Inventory.objects.filter(
            status=Inventory.BatchStatus.ACTIVE,
            surplus_status__in=[
                Inventory.SurplusStatus.NONE,
                Inventory.SurplusStatus.SURPLUS_EXPIRED,
            ],
            expiry_date__lte=cutoff.date(),
        )

        count = 0

        for batch in batches:
            # Surplus expiry must not exceed batch expiry date
            expiry_dt = datetime.combine(batch.expiry_date, time(23, 59, 59))
            expiry_dt = make_aware(expiry_dt)

            batch.surplus_discount_percentage = 50
            batch.surplus_expiry = expiry_dt
            batch.surplus_status = Inventory.SurplusStatus.SURPLUS_ACTIVE
            batch.save(update_fields=[
                "surplus_discount_percentage",
                "surplus_expiry",
                "surplus_status"
            ])

            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=None,  # system action
                event_type="reduction_started",
                snapshot_discount=50,
                snapshot_expiry=expiry_dt,
                snapshot_note="Automatic 50% reduction applied",
            )

            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Automatic 50% reductions applied to {count} batches expiring within 96 hours."
            )
        )
