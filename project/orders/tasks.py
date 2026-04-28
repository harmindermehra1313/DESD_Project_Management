"""
Background tasks executed by Django Q cluster.

– process_recurring_orders():  scheduled daily, creates new Order records
  from active RecurringOrder entries whose delivery_day matches today.
– send_order_email():  async helper to send transactional email without
  blocking the request/response cycle.
"""

import logging
from datetime import date

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "MON",
    1: "TUE",
    2: "WED",
    3: "THU",
    4: "FRI",
    5: "SAT",
    6: "SUN",
}


def process_recurring_orders():
    """Create orders for every active RecurringOrder whose delivery_day is today."""
    from orders.models import RecurringOrder, Order, OrderItem

    today_code = DAY_MAP[date.today().weekday()]

    due = RecurringOrder.objects.filter(
        status=RecurringOrder.Status.ACTIVE,
        delivery_day=today_code,
    ).select_related("user", "delivery_address")

    created_count = 0
    for ro in due:
        items = ro.items.select_related("product")
        if not items.exists():
            logger.warning("RecurringOrder #%s has no items – skipped.", ro.pk)
            continue

        order = Order.objects.create(
            user=ro.user,
            delivery_address=ro.delivery_address,
            recurring_order=ro,
            status=Order.Status.PENDING,
        )

        for ri in items:
            OrderItem.objects.create(
                order=order,
                product=ri.product,
                inventory=ri.product.inventories.first(),
                producer=ri.product.producer,
                quantity=ri.quantity,
                original_unit_price=ri.product.price,
                final_unit_price=ri.product.price,
                preparation_deadline=order.order_date,
            )

        logger.info("Created Order #%s from RecurringOrder #%s", order.pk, ro.pk)
        created_count += 1

        # Send confirmation email (non-blocking via Q if called from schedule)
        if ro.user and ro.user.email:
            send_order_email(
                subject="Your recurring order has been placed",
                message=f"Hi {ro.user.first_name},\n\n"
                        f"Your recurring order #{order.unique_reference} has been "
                        f"automatically placed.\n\nThank you!",
                recipient=ro.user.email,
            )

    logger.info("Recurring-order run complete: %d order(s) created.", created_count)
    return created_count


def send_order_email(subject, message, recipient):
    """Send a single transactional email. Designed to be queued via async_task()."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info("Email sent to %s", recipient)
    except Exception:
        logger.exception("Failed to send email to %s", recipient)
