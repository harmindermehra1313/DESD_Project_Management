# docker compose exec web python manage.py shell
# exec(open("orders/tests/debug/debug_demo_refund_service.py").read())

from decimal import Decimal

from django.db import transaction

from orders.models import Order
from payments.models import Payment, PaymentRefund
from payments.services import create_customer_refund


ORDER_ID = 41


class RollbackDebugChanges(Exception):
    pass


def print_result(case_id, result, details=""):
    print(f"{case_id}: {result}")
    if details:
        print(f"  Details: {details}")
    print("-" * 80)


try:
    with transaction.atomic():
        order = Order.objects.get(id=ORDER_ID)
        payment = order.payments.order_by("-created_at").first()

        print("=" * 80)
        print("DEMO REFUND SERVICE DEBUG")
        print("=" * 80)
        print(f"Order: #{order.id}")
        print(f"Payment: #{payment.id}")
        print(f"Payment status before: {payment.payment_status}")
        print(f"Payment amount: {payment.amount}")
        print(f"Stripe PaymentIntent: {payment.stripe_payment_intent}")
        print(f"Sandbox mode: {payment.sandbox_mode}")
        print("=" * 80)

        refund_count_before = PaymentRefund.objects.filter(payment=payment).count()

        result_1 = create_customer_refund(
            order=order,
            amount=Decimal("2.00"),
            reason="DEBUG demo refund test",
            order_item=None,
            idempotency_key=f"debug-order-{order.id}-demo-refund-test",
        )

        payment.refresh_from_db()
        refund_count_after_first = PaymentRefund.objects.filter(payment=payment).count()

        first_ok = (
            result_1.get("refunded") is True
            and result_1.get("simulated") is True
            and result_1.get("already_processed") is False
            and refund_count_after_first == refund_count_before + 1
        )

        print_result(
            "REFUND-DEBUG-001",
            "PASS" if first_ok else "FAIL",
            f"First refund result: {result_1}. Payment status now: {payment.payment_status}",
        )

        result_2 = create_customer_refund(
            order=order,
            amount=Decimal("2.00"),
            reason="DEBUG duplicate demo refund test",
            order_item=None,
            idempotency_key=f"debug-order-{order.id}-demo-refund-test",
        )

        payment.refresh_from_db()
        refund_count_after_second = PaymentRefund.objects.filter(payment=payment).count()

        duplicate_ok = (
            result_2.get("refunded") is True
            and result_2.get("simulated") is True
            and result_2.get("already_processed") is True
            and refund_count_after_second == refund_count_after_first
        )

        print_result(
            "REFUND-DEBUG-002",
            "PASS" if duplicate_ok else "FAIL",
            (
                f"Duplicate refund result: {result_2}. "
                f"Refund count before: {refund_count_before}, "
                f"after first: {refund_count_after_first}, "
                f"after second: {refund_count_after_second}."
            ),
        )

        print("=" * 80)
        print("DEBUG COMPLETE. ROLLING BACK DATABASE CHANGES NOW.")
        print("=" * 80)

        raise RollbackDebugChanges()

except RollbackDebugChanges:
    print("Rollback complete. Database has not been permanently changed.")