"""
Background tasks executed by Django Q cluster.

– process_recurring_orders():  scheduled daily, creates new Order records
  from active RecurringOrder entries.
- send_recurring_order_reminders(): scheduled daily, sends 72hr warning.
– send_order_email():  async helper to send transactional email without
  blocking the request/response cycle.
"""

import logging
from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "MON", 1: "TUE", 2: "WED", 3: "THU", 
    4: "FRI", 5: "SAT", 6: "SUN"
}
DAY_MAP_INV = {v: k for k, v in DAY_MAP.items()}

def is_order_due_on_date(recurring_order, target_date):
    """
    Deterministically calculates if a recurring order is due on a specific date 
    without needing extra database fields.
    """
    target_weekday = DAY_MAP_INV.get(recurring_order.delivery_day)
    
    # 1. Check if the target date is the correct day of the week
    if target_date.weekday() != target_weekday:
        return False
        
    # 2. Find the very first delivery date (anchor date) based on created_at
    created_date = recurring_order.created_at.date()
    days_ahead = target_weekday - created_date.weekday()
    if days_ahead < 0: # Target day already passed in the week it was created
        days_ahead += 7
    anchor_date = created_date + timedelta(days=days_ahead)
    
    # 3. Cannot be due before it starts
    if target_date < anchor_date:
        return False
        
    # 4. Check the frequency pattern
    if recurring_order.recurrence_pattern == "WEEKLY":
        return True
    elif recurring_order.recurrence_pattern == "FORTNIGHTLY":
        days_since_anchor = (target_date - anchor_date).days
        return days_since_anchor % 14 == 0
        
    return False

def process_recurring_orders():
    """Create orders for active RecurringOrders due today."""
    from orders.models import RecurringOrder, Order, OrderItem

    today = date.today()
    today_code = DAY_MAP[today.weekday()]

    # Filter by day of the week first to lighten the load
    potential_due = RecurringOrder.objects.filter(
        status=RecurringOrder.Status.ACTIVE,
        delivery_day=today_code,
    ).select_related("user", "delivery_address")

    created_count = 0
    for ro in potential_due:
        # Check the deterministic math for fortnightly schedules
        if not is_order_due_on_date(ro, today):
            continue

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
                inventory=ri.product.inventory_batches.first(),
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
                message=f"Hi {ro.user.name},\n\nYour recurring order #{order.unique_reference} has been automatically placed.\n\nThank you!",
                recipient=ro.user.email,
            )

    logger.info("Recurring-order run complete: %d order(s) created.", created_count)
    return created_count

def send_recurring_order_reminders():
    """Scheduled daily: Sends an email to users whose recurring order processes in 72 hours."""
    from orders.models import RecurringOrder
    
    target_date = date.today() + timedelta(days=3)
    target_code = DAY_MAP[target_date.weekday()]

    # Grab orders that land on the target day of the week
    potential_due = RecurringOrder.objects.filter(
        status=RecurringOrder.Status.ACTIVE,
        delivery_day=target_code
    ).select_related("user")

    for ro in potential_due:
        # Only email if the math says it's actually due in 3 days (ignores off-weeks for fortnightly)
        if is_order_due_on_date(ro, target_date):
            if ro.user and ro.user.email:
                async_task(
                    'orders.tasks.send_order_email',
                    subject="Your recurring order is coming up!",
                    message=f"Hi {ro.user.name},\n\nJust a heads up that your recurring order will be processed in 72 hours on {target_date}.\nIf you need to make changes, please log into your account.",
                    recipient=ro.user.email
                )

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