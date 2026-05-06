# docker compose exec web python manage.py shell
# exec(open("orders/tests/debug/debug_payment_refund_readiness.py").read())

from decimal import Decimal
from django.db.models import Sum
from django.contrib.auth import get_user_model

from orders.models import Order, OrderItem, ProducerOrderSummary
from payments.models import Payment, ProducerSettlement
from payments.stripe_client import get_stripe


CUSTOMER_EMAIL = "user1@gmail.com"

# Optional: set this to a specific order ID.
# Leave as None to automatically select the latest successful card-paid order.
ORDER_ID = None


User = get_user_model()
stripe = get_stripe()


def print_section(title):
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_line(label, value):
    print(f"{label}: {value}")


def money_from_pence(value):
    return Decimal(value or 0) / Decimal("100")


def get_debug_order():
    if ORDER_ID is not None:
        return Order.objects.get(id=ORDER_ID)

    order = (
        Order.objects
        .filter(
            user__email=CUSTOMER_EMAIL,
            payments__payment_method=Payment.Method.CARD,
            payments__payment_status=Payment.Status.SUCCESS,
        )
        .distinct()
        .order_by("-id")
        .first()
    )

    if order:
        return order

    return (
        Order.objects
        .filter(user__email=CUSTOMER_EMAIL)
        .distinct()
        .order_by("-id")
        .first()
    )


def get_latest_payment(order):
    return (
        Payment.objects
        .filter(order=order)
        .order_by("-created_at")
        .first()
    )


def get_latest_successful_card_payment(order):
    return (
        Payment.objects
        .filter(
            order=order,
            payment_method=Payment.Method.CARD,
            payment_status=Payment.Status.SUCCESS,
        )
        .order_by("-created_at")
        .first()
    )


def get_existing_refund_total_if_model_exists(payment):
    try:
        from payments.models import PaymentRefund
    except ImportError:
        return None

    total = (
        PaymentRefund.objects
        .filter(
            payment=payment,
            status=PaymentRefund.Status.SUCCEEDED,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
    )

    return total or Decimal("0.00")


def print_order_summary(order):
    print_section("ORDER")
    print_line("Order ID", order.id)
    print_line("Customer", getattr(order.user, "email", None))
    print_line("Order status", f"{order.status} / {order.get_status_display()}")
    print_line("Total price", order.total_price)
    print_line("Final total price", getattr(order, "final_total_price", None))
    print_line("Order date", order.order_date)


def print_payments(order):
    print_section("PAYMENTS")

    payments = list(
        Payment.objects
        .filter(order=order)
        .order_by("-created_at")
    )

    if not payments:
        print("No payments found for this order.")
        return

    for payment in payments:
        print("-" * 80)
        print_line("Payment ID", payment.id)
        print_line("Method", f"{payment.payment_method} / {payment.get_payment_method_display()}")
        print_line("Status", f"{payment.payment_status} / {payment.get_payment_status_display()}")
        print_line("Amount", payment.amount)
        print_line("Stripe PaymentIntent", payment.stripe_payment_intent)
        print_line("Transaction reference", payment.transaction_reference)
        print_line("Card", f"{payment.card_brand or '-'} ****{payment.card_last4 or '----'}")
        print_line("Sandbox mode", payment.sandbox_mode)


def print_producer_settlements(order):
    print_section("PRODUCER SETTLEMENT / PAYOUT CHECK")

    settlements = (
        ProducerSettlement.objects
        .filter(line_items__order_item__order=order)
        .distinct()
        .order_by("id")
    )

    if not settlements.exists():
        print("No ProducerSettlement rows found for this order.")
        print("Interpretation: producers have not been paid through the local settlement model.")
        return

    for settlement in settlements:
        print("-" * 80)
        print_line("Settlement ID", settlement.id)
        print_line("Producer ID", settlement.producer_id)
        print_line("Settlement week", settlement.settlement_week)
        print_line("Payout status", f"{settlement.payout_status} / {settlement.get_payout_status_display()}")
        print_line("Total sales", settlement.total_sales)
        print_line("Commission", settlement.total_commission)
        print_line("Payout amount", settlement.payout_amount)
        print_line("Payment reference", settlement.payment_reference)


def print_producer_summaries(order):
    print_section("PRODUCER ORDER SUMMARIES")

    summaries = (
        ProducerOrderSummary.objects
        .filter(order=order)
        .select_related("producer")
        .order_by("id")
    )

    if not summaries.exists():
        print("No producer summaries found.")
        return

    for summary in summaries:
        print("-" * 80)
        print_line("Summary ID", summary.id)
        print_line("Producer", getattr(summary.producer, "farm_name", summary.producer_id))
        print_line("Status", f"{summary.status} / {summary.get_status_display()}")
        print_line("Subtotal", summary.subtotal)
        print_line("Commission total", summary.commission_total)
        print_line("Payout amount", summary.payout_amount)


def print_items_and_refund_candidates(order):
    print_section("ITEM REFUND CANDIDATES")

    items = (
        OrderItem.objects
        .filter(order=order)
        .select_related("product", "producer", "inventory")
        .order_by("id")
    )

    if not items.exists():
        print("No order items found.")
        return

    for item in items:
        active_quantity = max(item.quantity - item.cancelled_quantity, 0)
        candidate_amount = Decimal(item.final_unit_price) * Decimal(active_quantity)

        summary = (
            ProducerOrderSummary.objects
            .filter(order=order, producer_id=item.producer_id)
            .first()
        )

        can_cancel_item = (
            order.status not in {Order.Status.CANCELLED, Order.Status.COMPLETED}
            and item.status != OrderItem.Status.CANCELLED
            and summary is not None
            and summary.status == ProducerOrderSummary.Status.PENDING
            and active_quantity > 0
        )

        print("-" * 80)
        print_line("Item ID", item.id)
        print_line("Product", getattr(item.product, "name", item.product_id))
        print_line("Producer", getattr(item.producer, "farm_name", item.producer_id))
        print_line("Item status", f"{item.status} / {item.get_status_display()}")
        print_line("Original quantity", item.quantity)
        print_line("Cancelled quantity", item.cancelled_quantity)
        print_line("Active quantity", active_quantity)
        print_line("Final unit price", item.final_unit_price)
        print_line("Refund candidate amount", candidate_amount)
        print_line("Producer summary status", summary.status if summary else "Missing summary")
        print_line("Can auto-cancel/refund item now", can_cancel_item)


def print_local_refund_readiness(order):
    print_section("LOCAL REFUND READINESS")

    payment = get_latest_successful_card_payment(order)

    if payment is None:
        latest_payment = get_latest_payment(order)

        print("No successful card payment found for this order.")
        if latest_payment:
            print_line("Latest payment method", latest_payment.get_payment_method_display())
            print_line("Latest payment status", latest_payment.get_payment_status_display())
        print("Interpretation: automatic Stripe refund cannot be created from this order yet.")
        return None

    print_line("Successful card payment ID", payment.id)
    print_line("Payment amount", payment.amount)
    print_line("Stripe PaymentIntent", payment.stripe_payment_intent)

    existing_refund_total = get_existing_refund_total_if_model_exists(payment)

    if existing_refund_total is None:
        print("PaymentRefund model not found yet.")
        print("Interpretation: refund tracking model still needs to be added before safe refund implementation.")
    else:
        remaining = payment.amount - existing_refund_total
        print_line("Existing succeeded local refund total", existing_refund_total)
        print_line("Remaining locally refundable amount", remaining)

    if not payment.stripe_payment_intent:
        print("Problem: Payment has no Stripe PaymentIntent reference.")
        print("Automatic Stripe refund needs stripe_payment_intent.")

    return payment


def print_stripe_payment_intent(payment):
    print_section("STRIPE PAYMENTINTENT CHECK")

    if payment is None:
        print("Skipped: no successful card payment available.")
        return

    if not payment.stripe_payment_intent:
        print("Skipped: payment has no Stripe PaymentIntent ID.")
        return

    try:
        payment_intent = stripe.PaymentIntent.retrieve(
            payment.stripe_payment_intent,
            expand=["latest_charge", "payment_method"],
        )
    except Exception as exc:
        print(f"Stripe retrieve failed: {type(exc).__name__}: {exc}")
        print("Check STRIPE_SECRET_KEY, network access, and whether this PaymentIntent exists in the same Stripe mode.")
        return

    print_line("Stripe PaymentIntent ID", payment_intent.get("id"))
    print_line("Stripe status", payment_intent.get("status"))
    print_line("Currency", payment_intent.get("currency"))
    print_line("Amount", money_from_pence(payment_intent.get("amount")))
    print_line("Amount received", money_from_pence(payment_intent.get("amount_received")))

    latest_charge = payment_intent.get("latest_charge")

    if not isinstance(latest_charge, dict):
        print("No expanded latest_charge found.")
        return

    amount = latest_charge.get("amount") or 0
    amount_refunded = latest_charge.get("amount_refunded") or 0
    remaining_refundable = Decimal(amount - amount_refunded) / Decimal("100")

    print("-" * 80)
    print_line("Latest charge ID", latest_charge.get("id"))
    print_line("Charge status", latest_charge.get("status"))
    print_line("Charge paid", latest_charge.get("paid"))
    print_line("Charge refunded fully", latest_charge.get("refunded"))
    print_line("Charge amount", money_from_pence(amount))
    print_line("Charge amount refunded", money_from_pence(amount_refunded))
    print_line("Remaining Stripe refundable amount", remaining_refundable)


order = get_debug_order()

if not order:
    print(f"No orders found for {CUSTOMER_EMAIL}.")
else:
    print_order_summary(order)
    print_payments(order)
    print_producer_settlements(order)
    print_producer_summaries(order)
    print_items_and_refund_candidates(order)
    payment = print_local_refund_readiness(order)
    print_stripe_payment_intent(payment)

    print_section("DEBUG COMPLETE")
    print("No database changes were made by this script.")