from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from payments.models import Payment, PaymentRefund
from payments.stripe_client import get_stripe


stripe = get_stripe()

MIN_ORDER = Decimal("1.00")


class CustomerRefundError(Exception):
    """Raised when a customer refund cannot be completed."""

    pass


def money_to_pence(amount):
    return int(
        (Decimal(amount) * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def normalise_money(amount):
    return Decimal(amount).quantize(Decimal("0.01"))


def create_payment_intent(amount, session_key=None, user_id=None):
    amount = normalise_money(amount)

    if amount < MIN_ORDER:
        raise ValidationError("Minimum order amount is £1.00")

    return stripe.PaymentIntent.create(
        amount=money_to_pence(amount),
        currency="gbp",
        payment_method_types=["card"],
        metadata={
            "session_key": session_key or "",
            "user_id": user_id or "",
        },
        setup_future_usage=None,
    )


def create_transfer(producer, amount, order):
    amount = normalise_money(amount)

    return stripe.Transfer.create(
        amount=money_to_pence(amount),
        currency="gbp",
        destination=producer.stripe_account_id,
        transfer_group=f"order_{order.id}",
    )


def is_demo_stripe_payment(payment):
    return (
        payment.sandbox_mode is True
        and bool(payment.stripe_payment_intent)
        and payment.stripe_payment_intent.startswith("pi_demo_")
    )


def get_successful_card_payment_for_order(order):
    return (
        Payment.objects.select_for_update()
        .filter(
            order=order,
            payment_method=Payment.Method.CARD,
            payment_status__in=[
                Payment.Status.SUCCESS,
                Payment.Status.PARTIALLY_REFUNDED,
                Payment.Status.REFUNDED,
            ],
        )
        .order_by("-created_at")
        .first()
    )


def get_succeeded_refund_total(payment):
    total = (
        PaymentRefund.objects.filter(
            payment=payment,
            status=PaymentRefund.Status.SUCCEEDED,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
    )

    return total or Decimal("0.00")


def update_payment_refund_status(payment):
    refunded_total = get_succeeded_refund_total(payment)

    if refunded_total <= Decimal("0.00"):
        return payment

    if refunded_total >= payment.amount:
        payment.payment_status = Payment.Status.REFUNDED
    else:
        payment.payment_status = Payment.Status.PARTIALLY_REFUNDED

    payment.save(update_fields=["payment_status"])
    return payment


def build_refund_response(
    *,
    refunded,
    amount,
    refund_record=None,
    reason="",
    simulated=False,
    already_processed=False,
    message="",
):
    response = {
        "refunded": refunded,
        "simulated": simulated,
        "already_processed": already_processed,
        "amount": str(normalise_money(amount)),
    }

    if refund_record is not None:
        response.update(
            {
                "refund_id": refund_record.id,
                "stripe_refund_id": refund_record.stripe_refund_id,
                "status": refund_record.status,
            }
        )

    if reason:
        response["reason"] = reason

    if message:
        response["message"] = message

    return response


def get_or_create_locked_refund_record(
    *,
    payment,
    order,
    order_item,
    amount,
    reason,
    idempotency_key,
):
    existing_refund = (
        PaymentRefund.objects.select_for_update()
        .filter(idempotency_key=idempotency_key)
        .first()
    )

    if existing_refund:
        if existing_refund.amount != amount:
            raise CustomerRefundError(
                "Existing refund idempotency key was reused with a different amount."
            )

        return existing_refund, False

    refund_record = PaymentRefund.objects.create(
        payment=payment,
        order=order,
        order_item=order_item,
        amount=amount,
        reason=reason,
        idempotency_key=idempotency_key,
        status=PaymentRefund.Status.PENDING,
    )

    return refund_record, True


def complete_demo_refund(refund_record, payment):
    if refund_record.status == PaymentRefund.Status.SUCCEEDED:
        return build_refund_response(
            refunded=True,
            amount=refund_record.amount,
            refund_record=refund_record,
            simulated=True,
            already_processed=True,
            message="Demo refund was already processed.",
        )

    refund_record.stripe_refund_id = (
        refund_record.stripe_refund_id or f"demo_refund_{refund_record.id}"
    )
    refund_record.status = PaymentRefund.Status.SUCCEEDED
    refund_record.error_message = ""
    refund_record.save(
        update_fields=[
            "stripe_refund_id",
            "status",
            "error_message",
            "updated_at",
        ]
    )

    update_payment_refund_status(payment)

    return build_refund_response(
        refunded=True,
        amount=refund_record.amount,
        refund_record=refund_record,
        simulated=True,
        already_processed=False,
        message="Demo refund simulated locally.",
    )


def complete_stripe_refund(refund_record, payment, order, order_item, idempotency_key):
    if refund_record.status == PaymentRefund.Status.SUCCEEDED:
        return build_refund_response(
            refunded=True,
            amount=refund_record.amount,
            refund_record=refund_record,
            simulated=False,
            already_processed=True,
            message="Refund was already processed.",
        )

    if refund_record.stripe_refund_id:
        return build_refund_response(
            refunded=True,
            amount=refund_record.amount,
            refund_record=refund_record,
            simulated=False,
            already_processed=True,
            message="Stripe refund request already exists.",
        )

    try:
        stripe_refund = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent,
            amount=money_to_pence(refund_record.amount),
            reason="requested_by_customer",
            metadata={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "order_item_id": str(order_item.id) if order_item else "",
                "refund_record_id": str(refund_record.id),
            },
            idempotency_key=idempotency_key,
        )

    except Exception as exc:
        refund_record.status = PaymentRefund.Status.FAILED
        refund_record.error_message = str(exc)
        refund_record.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at",
            ]
        )
        raise CustomerRefundError(str(exc)) from exc

    refund_record.stripe_refund_id = stripe_refund.get("id", "")
    refund_record.status = (
        PaymentRefund.Status.SUCCEEDED
        if stripe_refund.get("status") == "succeeded"
        else PaymentRefund.Status.PENDING
    )
    refund_record.error_message = ""
    refund_record.save(
        update_fields=[
            "stripe_refund_id",
            "status",
            "error_message",
            "updated_at",
        ]
    )

    update_payment_refund_status(payment)

    return build_refund_response(
        refunded=True,
        amount=refund_record.amount,
        refund_record=refund_record,
        simulated=False,
        already_processed=False,
        message="Stripe refund requested.",
    )


def create_customer_refund(
    *,
    order,
    amount,
    reason,
    order_item=None,
    idempotency_key,
):
    amount = normalise_money(amount)
    reason = (reason or "").strip() or "Customer refund requested"

    if amount <= Decimal("0.00"):
        return build_refund_response(
            refunded=False,
            amount=Decimal("0.00"),
            reason="Refund amount must be greater than zero.",
        )

    with transaction.atomic():
        payment = get_successful_card_payment_for_order(order)

        if payment is None:
            return build_refund_response(
                refunded=False,
                amount=Decimal("0.00"),
                reason="No successful card payment found for this order.",
            )

        if not payment.stripe_payment_intent:
            return build_refund_response(
                refunded=False,
                amount=Decimal("0.00"),
                reason="Payment does not have a Stripe PaymentIntent reference.",
            )

        already_refunded = get_succeeded_refund_total(payment)
        remaining_refundable = normalise_money(payment.amount - already_refunded)

        existing_refund = (
            PaymentRefund.objects.select_for_update()
            .filter(idempotency_key=idempotency_key)
            .first()
        )

        if existing_refund and existing_refund.status == PaymentRefund.Status.SUCCEEDED:
            return build_refund_response(
                refunded=True,
                amount=existing_refund.amount,
                refund_record=existing_refund,
                simulated=existing_refund.stripe_refund_id.startswith("demo_refund_"),
                already_processed=True,
                message="Refund was already processed.",
            )

        if remaining_refundable <= Decimal("0.00"):
            return build_refund_response(
                refunded=False,
                amount=Decimal("0.00"),
                reason="Payment has already been fully refunded.",
            )

        if amount > remaining_refundable:
            raise CustomerRefundError(
                "Refund amount cannot be greater than the remaining refundable payment amount."
            )

        refund_record, _created = get_or_create_locked_refund_record(
            payment=payment,
            order=order,
            order_item=order_item,
            amount=amount,
            reason=reason,
            idempotency_key=idempotency_key,
        )

        if is_demo_stripe_payment(payment):
            return complete_demo_refund(
                refund_record=refund_record,
                payment=payment,
            )

        return complete_stripe_refund(
            refund_record=refund_record,
            payment=payment,
            order=order,
            order_item=order_item,
            idempotency_key=idempotency_key,
        )


def refund_remaining_card_payment_for_order(*, order, reason):
    with transaction.atomic():
        payment = get_successful_card_payment_for_order(order)

        if payment is None:
            return build_refund_response(
                refunded=False,
                amount=Decimal("0.00"),
                reason="No successful card payment found for this order.",
            )

        already_refunded = get_succeeded_refund_total(payment)
        remaining_refundable = normalise_money(payment.amount - already_refunded)

        if remaining_refundable <= Decimal("0.00"):
            return build_refund_response(
                refunded=False,
                amount=Decimal("0.00"),
                reason="Payment has already been fully refunded.",
            )

    return create_customer_refund(
        order=order,
        amount=remaining_refundable,
        reason=reason,
        order_item=None,
        idempotency_key=f"order-{order.id}-full-customer-refund",
    )


def refund_cancelled_order_item(*, order, item, cancelled_quantity, reason):
    cancelled_quantity = int(cancelled_quantity)
    amount = normalise_money(Decimal(item.final_unit_price) * Decimal(cancelled_quantity))

    return create_customer_refund(
        order=order,
        amount=amount,
        reason=reason,
        order_item=item,
        idempotency_key=f"order-{order.id}-item-{item.id}-customer-refund",
    )