# docker compose exec web python manage.py populate_payments  --clear
import random
import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from orders.models import Order
from payments.models import Payment


DEMO_CARDS = [
    {"brand": "Visa", "last4": "4242"},
    {"brand": "Visa", "last4": "1111"},
    {"brand": "Mastercard", "last4": "4444"},
    {"brand": "Mastercard", "last4": "5100"},
    {"brand": "American Express", "last4": "0005"},
]


PAYMENT_METHOD_WEIGHTS = [
    (Payment.Method.CARD, 80),
    (Payment.Method.ACCOUNT_WALLET, 10),
    (Payment.Method.VOUCHER, 6),
    (Payment.Method.CASH, 4),
]


class Command(BaseCommand):
    help = "Populate payments for existing orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=None,
            help="Number of orders to create payments for. Default: all eligible orders.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing payments before creating new ones.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        if count is not None and count < 1:
            raise CommandError("--count must be greater than 0.")

        if clear:
            deleted_count, _ = Payment.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing payment data. Deleted rows: {deleted_count}"
                )
            )

        orders = self._get_orders_for_payment_creation(count=count)

        if not orders:
            raise CommandError(
                "No eligible orders found. Run populate_orders first, "
                "or use --clear if existing payments should be regenerated."
            )

        created_count = 0
        skipped_count = 0

        for order in orders:
            if not clear and order.payments.exists():
                skipped_count += 1
                continue

            with transaction.atomic():
                self._create_payment_for_order(order=order)

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Payment population complete: "
                f"{created_count} payments created, "
                f"{skipped_count} orders skipped."
            )
        )

    def _get_orders_for_payment_creation(self, count):
        queryset = (
            Order.objects.prefetch_related("payments")
            .filter(final_total_price__gt=Decimal("0.00"))
            .order_by("order_date", "id")
        )

        if count is not None:
            queryset = queryset[:count]

        return list(queryset)

    def _create_payment_for_order(self, order):
        payment_method = self._weighted_choice(PAYMENT_METHOD_WEIGHTS)
        payment_status = self._payment_status_for_order(order=order)

        card_brand = None
        card_last4 = None
        stripe_payment_intent = None

        if payment_method == Payment.Method.CARD:
            card = random.choice(DEMO_CARDS)
            card_brand = card["brand"]
            card_last4 = card["last4"]
            stripe_payment_intent = self._build_stripe_payment_intent()

        Payment.objects.create(
            order=order,
            stripe_payment_intent=stripe_payment_intent,
            card_brand=card_brand,
            card_last4=card_last4,
            amount=self._money(order.final_total_price),
            payment_method=payment_method,
            payment_status=payment_status,
            transaction_reference=self._build_transaction_reference(order=order),
            sandbox_mode=True,
        )

    def _payment_status_for_order(self, order):
        """
        Derive payment status from order status.

        Current order lifecycle:
        - Pending order -> Pending payment
        - In-progress order -> Successful payment
        - Completed order -> Successful payment

        Cancelled/refunded handling is kept here for safety in case older
        seeded orders still contain cancelled statuses.
        """
        if order.status == Order.Status.PENDING:
            return Payment.Status.PENDING

        if order.status in {
            Order.Status.IN_PROGRESS,
            Order.Status.PACKAGED,
            Order.Status.READY_FOR_COLLECTION,
            Order.Status.COMPLETED,
        }:
            return Payment.Status.SUCCESS

        if order.status == Order.Status.CANCELLED:
            return random.choice(
                [
                    Payment.Status.REFUNDED,
                    Payment.Status.FAILED,
                ]
            )

        return Payment.Status.PENDING

    def _build_transaction_reference(self, order):
        return f"DEMO-PAY-{order.pk}-{uuid.uuid4().hex[:10].upper()}"

    def _build_stripe_payment_intent(self):
        return f"pi_demo_{uuid.uuid4().hex}"

    def _weighted_choice(self, choices):
        values = [value for value, _weight in choices]
        weights = [weight for _value, weight in choices]

        return random.choices(values, weights=weights, k=1)[0]

    def _money(self, value):
        return Decimal(value).quantize(Decimal("0.01"))