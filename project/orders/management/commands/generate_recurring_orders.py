"""
Generate physical orders from active recurring-order templates.

Run daily (e.g. via cron) to create orders whose delivery day matches today:

    python manage.py generate_recurring_orders

Pass --dry-run to preview without writing to the database.

Logic
-----
1. Find every RecurringOrder with status ACTIVE.
2. Skip if the initial order has not yet been delivered / completed.
3. Determine whether a new order is due today:
   - The recurrence_day on the template must match today's weekday.
   - For FORTNIGHTLY templates, ensure at least 14 days since the last
     generated order; for WEEKLY, at least 7 days.
4. Create a new Order (+ OrderItem, ProducerOrderSummary, Payment) that
   mirrors the template.
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    RecurringOrder,
    RecurringOrderItem,
)
from payments.models import Payment
from notifications.models import TraceabilityRecord

DAY_CODE_TO_WEEKDAY = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


class Command(BaseCommand):
    help = "Generate physical orders from active recurring-order templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview orders that would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        today_weekday = today.weekday()  # 0 = Monday

        active_templates = (
            RecurringOrder.objects.filter(status=RecurringOrder.Status.ACTIVE)
            .select_related("user", "delivery_address")
            .prefetch_related("items__product__producer", "items__product__category")
        )

        created_count = 0
        skipped_count = 0

        for template in active_templates:
            # ---- Day-of-week gate (uses recurrence_day: the day the order repeats on) ----
            expected_weekday = DAY_CODE_TO_WEEKDAY.get(template.recurrence_day)
            if expected_weekday is None or today_weekday != expected_weekday:
                continue

            # ---- Initial order must be delivered ----
            initial_order = (
                template.generated_orders.order_by("order_date").first()
            )
            if initial_order is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Template #{template.pk}: no initial order found – skipping."
                    )
                )
                skipped_count += 1
                continue

            # Check if initial order is completed/shipped
            initial_delivered = initial_order.status in (
                Order.Status.COMPLETED,
                Order.Status.OUT_FOR_DELIVERY,
            )
            if not initial_delivered:
                # Also check producer summaries for shipped status
                all_shipped = initial_order.producer_summaries.exists() and all(
                    s.status in (
                        ProducerOrderSummary.Status.SHIPPED,
                        ProducerOrderSummary.Status.COMPLETED,
                    )
                    for s in initial_order.producer_summaries.all()
                )
                if not all_shipped:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Template #{template.pk}: initial order not yet delivered – skipping."
                        )
                    )
                    skipped_count += 1
                    continue

            # ---- Frequency gate ----
            last_generated = (
                template.generated_orders.order_by("-order_date").first()
            )
            if last_generated:
                days_since = (today - last_generated.order_date.date()).days
                min_gap = 14 if template.recurrence_pattern == RecurringOrder.RecurrencePattern.FORTNIGHTLY else 7
                if days_since < min_gap:
                    skipped_count += 1
                    continue

            # ---- Eligible — create the order ----
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [DRY-RUN] Would create order for template #{template.pk} "
                        f"(user={template.user}, pattern={template.get_recurrence_pattern_display()}, "
                        f"repeats on={template.get_recurrence_day_display()})"
                    )
                )
                created_count += 1
                continue

            try:
                order = self._create_order_from_template(template, today)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created order #{order.unique_reference} for template #{template.pk}"
                    )
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Template #{template.pk}: failed – {exc}"
                    )
                )
                skipped_count += 1

        self.stdout.write(
            f"\nDone. Created: {created_count}, Skipped: {skipped_count}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @transaction.atomic
    def _create_order_from_template(self, template: RecurringOrder, delivery_date: datetime.date) -> Order:
        """Create a full Order mirroring the recurring template."""

        user = template.user
        delivery_address = template.delivery_address

        order = Order.objects.create(
            user=user,
            is_guest=False,
            delivery_address=delivery_address,
            billing_address=delivery_address,
            recurring_order=template,
            status=Order.Status.PENDING,
        )

        total_excl_vat = Decimal("0")
        total_vat = Decimal("0")
        total_discount = Decimal("0")
        commission_total = Decimal("0")
        commission_per = Decimal("0.05")

        items_by_producer: dict = {}

        for ro_item in template.items.select_related(
            "product", "product__producer", "product__category"
        ):
            product = ro_item.product
            producer = product.producer
            quantity = ro_item.quantity

            # Find the best available inventory batch
            inventory = (
                product.inventory_batches
                .filter(remaining_quantity__gte=quantity)
                .order_by("expiry_date")
                .first()
            )

            if inventory is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"    Product '{product.name}' out of stock – skipping item."
                    )
                )
                continue

            unit_price = inventory.get_discounted_price()
            original_unit_price = product.price
            original_line_total = original_unit_price * quantity
            line_total = unit_price * quantity
            discount_amount = original_line_total - line_total

            vat_rate = product.category.vat
            vat_fraction = vat_rate / Decimal("100")
            vat_amount = unit_price * vat_fraction * quantity

            commission_amount = line_total * commission_per

            total_excl_vat += line_total
            total_vat += vat_amount
            total_discount += discount_amount
            commission_total += commission_amount

            item = OrderItem.objects.create(
                order=order,
                inventory=inventory,
                product=product,
                producer=producer,
                quantity=quantity,
                original_unit_price=original_unit_price,
                final_unit_price=unit_price,
                vat_amount=vat_amount,
                vat_rate=vat_rate,
                commission_amount=commission_amount,
                discount_amount=discount_amount,
                preparation_deadline=timezone.now() + timezone.timedelta(hours=48),
            )

            # Traceability
            TraceabilityRecord.objects.create(
                order_item=item,
                inventory=inventory,
                product=product,
                producer=producer,
                customer=user.customer_profile if hasattr(user, "customer_profile") else None,
            )

            # Reduce stock
            inventory.remaining_quantity = max(inventory.remaining_quantity - quantity, 0)
            inventory.save(update_fields=["remaining_quantity"])

            items_by_producer.setdefault(producer, []).append(item)

        if not items_by_producer:
            raise ValueError("No items could be fulfilled – all products out of stock.")

        # Update order totals
        order.total_price = total_excl_vat
        order.total_vat = total_vat
        order.total_discount = total_discount
        order.total_commission = commission_total
        order.final_total_price = total_excl_vat + total_vat
        order.save()

        # Producer summaries
        for producer, producer_items in items_by_producer.items():
            addr = delivery_address
            subtotal = sum(i.final_unit_price * i.quantity for i in producer_items)
            vat_total_p = sum(i.vat_amount for i in producer_items)
            commission_total_p = sum(i.commission_amount for i in producer_items)
            payout_amount = subtotal - commission_total_p

            ProducerOrderSummary.objects.create(
                order=order,
                producer=producer,
                subtotal=subtotal,
                vat_total=vat_total_p,
                commission_total=commission_total_p,
                payout_amount=payout_amount,
                delivery_date=delivery_date,
                special_instructions=template.special_instructions or "",
                status=ProducerOrderSummary.Status.PENDING,
                delivery_or_collection=Order.DeliveryOrCollection.DELIVERY,
                address_line1=addr.line1 if addr else "",
                address_line2=addr.line2 if addr else "",
                city=addr.city if addr else "",
                postcode=addr.postcode if addr else "",
            )

        # Payment record (recurring orders are auto-billed)
        Payment.objects.create(
            order=order,
            amount=order.final_total_price,
            payment_method="COD",
            payment_status=Payment.Status.PENDING,
        )

        return order
