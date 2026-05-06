from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from decimal import Decimal

from payments.models import ProducerSettlement, SettlementLineItem
from orders.models import ProducerOrderSummary, OrderItem
from payments.stripe_connect import create_transfer
from notifications.services.notifications import NotificationService


class Command(BaseCommand):
    help = "Generate weekly producer settlements (Mon–Sun)."

    def handle(self, *args, **options):
        today = now().date()

        # Determine last week (Mon → Sun)
        weekday = today.weekday()  # Monday = 0
        last_sunday = today - timedelta(days=weekday + 1)
        last_monday = last_sunday - timedelta(days=6)

        self.stdout.write(
            self.style.NOTICE(f"Generating settlements for {last_monday} → {last_sunday}")
        )

        # Fetch all completed summaries for last week that are not settled
        summaries = ProducerOrderSummary.objects.filter(
            delivery_date__range=[last_monday, last_sunday],
            status=ProducerOrderSummary.Status.COMPLETED,
            settlement__isnull=True,
        ).select_related("producer", "order")

        if not summaries.exists():
            self.stdout.write(self.style.WARNING("No completed summaries found."))
            return

        # Group by producer
        producers = {}
        for summary in summaries:
            producers.setdefault(summary.producer, []).append(summary)

        # Process each producer
        for producer, producer_summaries in producers.items():

            total_sales = sum((s.subtotal for s in producer_summaries), Decimal("0.00"))
            total_commission = sum((s.commission_total for s in producer_summaries), Decimal("0.00"))
            payout_amount = sum((s.payout_amount for s in producer_summaries), Decimal("0.00"))

            # Create settlement record
            settlement = ProducerSettlement.objects.create(
                producer=producer,
                settlement_week=last_monday,
                total_sales=total_sales,
                total_commission=total_commission,
                payout_amount=payout_amount,
                payment_reference="",
                payout_status=ProducerSettlement.PayoutStatus.PENDING,
            )

            # Create line items
            for summary in producer_summaries:
                order_items = OrderItem.objects.filter(order=summary.order)

                for item in order_items:
                    SettlementLineItem.objects.create(
                        settlement=settlement,
                        order_item=item,
                        amount=item.original_unit_price * item.quantity,
                        commission=item.commission_amount,
                        net_amount=item.final_unit_price * item.quantity,
                    )

                # Mark summary as settled
                summary.settlement = settlement
                summary.save(update_fields=["settlement"])

            # If payout is zero, skip Stripe/manual payout
            if payout_amount <= 0:
                NotificationService.create_unique(
                    user=producer.user,
                    type="SYS",
                    message=(
                        f"You had no completed orders for {last_monday} → {last_sunday}, "
                        f"so no payout was generated."
                    ),
                )
                continue

            # STRIPE PAYOUT (if producer has a Stripe account)
            if producer.stripe_account_id:
                try:
                    transfer = create_transfer(settlement)

                    settlement.payment_reference = transfer.id
                    settlement.payout_status = ProducerSettlement.PayoutStatus.PROCESSING
                    settlement.save(update_fields=["payment_reference", "payout_status"])

                    NotificationService.create_unique(
                        user=producer.user,
                        type="SYS",
                        message=(
                            f"Your weekly payout of £{payout_amount:.2f} "
                            f"has been sent to your Stripe account."
                        ),
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Stripe payout sent for Producer #{producer.id}: £{payout_amount}"
                        )
                    )

                except Exception as e:
                    settlement.payout_status = ProducerSettlement.PayoutStatus.FAILED
                    settlement.payment_reference = f"STRIPE_ERROR: {str(e)}"
                    settlement.save(update_fields=["payment_reference", "payout_status"])

                    NotificationService.create_unique(
                        user=producer.user,
                        type="SYS",
                        message=(
                            "We were unable to send your payout via Stripe. "
                            "Please update your Stripe payout details."
                        ),
                    )

                    self.stdout.write(
                        self.style.ERROR(
                            f"Stripe payout FAILED for Producer #{producer.id}: {str(e)}"
                        )
                    )

                continue  # Skip manual fallback if Stripe exists


            # MANUAL PAYOUT FALLBACK
            settlement.payment_reference = "MANUAL_PAYOUT_REQUIRED"
            settlement.payout_status = ProducerSettlement.PayoutStatus.PENDING
            settlement.save(update_fields=["payment_reference", "payout_status"])

            NotificationService.create_unique(
                user=producer.user,
                type="SYS",
                message=(
                    f"A payout of £{payout_amount:.2f} has been generated for "
                    f"{last_monday} → {last_sunday}. "
                    "Since you have not connected Stripe, this will be paid manually."
                ),
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Manual payout required for Producer #{producer.id}: £{payout_amount}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Weekly settlements generated successfully."))
