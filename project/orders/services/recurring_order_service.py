"""
Service for creating orders from recurring order templates.
Used by the resume endpoint and the generate_recurring_orders command.
"""

import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    RecurringOrder,
)
from payments.models import Payment
from notifications.models import TraceabilityRecord


@transaction.atomic
def create_order_from_recurring_template(template: RecurringOrder, delivery_date: datetime.date) -> Order:
    """
    Create a full Order (with OrderItems, ProducerOrderSummaries, Payment,
    TraceabilityRecords) mirroring the given recurring-order template.

    Returns the created Order, or raises ValueError if no items could be
    fulfilled.
    """
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
            .filter(
                remaining_quantity__gte=quantity,
                expiry_date__gte=delivery_date
            )
            .order_by("expiry_date")
            .first()
        )

        if inventory is None:
            # Strict fulfillment: abort the entire order if any item is out of stock
            raise ValueError(f"Strict fulfillment failed: '{product.name}' is out of stock.")

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
        # Roll back – nothing could be created
        order.delete()
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
