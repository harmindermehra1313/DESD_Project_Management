import datetime
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order, RecurringOrder, ProducerOrderSummary
from orders.services.recurring_order_service import create_order_from_recurring_template

DAY_CODE_TO_WEEKDAY = {
    "MON": 0, "TUE": 1, "WED": 2, "THU": 3,
    "FRI": 4, "SAT": 5, "SUN": 6,
}
WEEKDAY_TO_CODE = {v: k for k, v in DAY_CODE_TO_WEEKDAY.items()}


def _next_valid_recurrence_date(recurrence_day_code, pattern, min_hours=48):
    """Return the next date matching recurrence_day that is at least
    *min_hours* from now. For FORTNIGHTLY, add 7 extra days if the first
    candidate is within the same week as the last generated order."""
    target_weekday = DAY_CODE_TO_WEEKDAY.get(recurrence_day_code)
    if target_weekday is None:
        return None

    now = timezone.now()
    cutoff = now + datetime.timedelta(hours=min_hours)
    candidate = cutoff.date()

    # Find the next day matching the target weekday
    days_ahead = (target_weekday - candidate.weekday()) % 7
    if days_ahead == 0:
        # The cutoff day IS the target weekday — check time
        if cutoff.date() == (now + datetime.timedelta(hours=min_hours)).date():
            candidate = candidate + datetime.timedelta(days=0)
        else:
            candidate = candidate + datetime.timedelta(days=7)
    else:
        candidate = candidate + datetime.timedelta(days=days_ahead)

    return candidate


@login_required
def list_recurring_page(request):
    """Display the customer's recurring orders / subscriptions."""

    # Fetch this customer's recurring orders (active + paused shown by default)
    recurring_qs = RecurringOrder.objects.filter(
        user=request.user,
    ).select_related('delivery_address').prefetch_related(
        'items__product__producer__user',
        'generated_orders',
    ).order_by('-created_at')

    customer_subscriptions = []
    for ro in recurring_qs:
        items_data = []
        producers = set()
        for item in ro.items.all():
            items_data.append({
                'product_name': item.product.name,
                'quantity': item.quantity,
                'unit': item.product.get_unit_display(),
                'price': str(item.product.price),
                'producer_name': item.product.producer.user.name if item.product.producer and item.product.producer.user else 'Unknown',
            })
            if item.product.producer and item.product.producer.user:
                producers.add(item.product.producer.user.name)

        # Find the nearest upcoming (pending) order for this subscription
        upcoming_order = ro.generated_orders.filter(
            status=Order.Status.PENDING,
        ).order_by('order_date').first()

        addr = ro.delivery_address
        address_data = None
        if addr:
            address_data = {
                'line_1': addr.line1,
                'line_2': addr.line2 or '',
                'city': addr.city,
                'postcode': addr.postcode,
            }

        customer_subscriptions.append({
            'id': ro.id,
            'status': ro.status,
            'status_display': ro.get_status_display(),
            'recurrence_pattern': ro.get_recurrence_pattern_display(),
            'recurrence_pattern_code': ro.recurrence_pattern,
            'recurrence_day': ro.get_recurrence_day_display(),
            'recurrence_day_code': ro.recurrence_day,
            'delivery_day': ro.get_delivery_day_display() if ro.delivery_day else 'Not Set',
            'address_data': address_data,
            'special_instructions': ro.special_instructions or '',
            'items': items_data,
            'producers': list(producers),
            'created_at': ro.created_at.isoformat() if ro.created_at else '',
            'upcoming_order_id': upcoming_order.id if upcoming_order else None,
            'upcoming_order_date': upcoming_order.order_date.isoformat() if upcoming_order else None,
        })

    return render(
        request,
        "orders/list_recurring.html",
        {
            "customer_subscriptions": customer_subscriptions,
            "status_choices": RecurringOrder.Status.choices,
            "frequency_choices": RecurringOrder.RecurrencePattern.choices,
            "day_choices": RecurringOrder.Day.choices,
        },
    )


@login_required
@require_POST
def customer_toggle_subscription(request, sub_id):
    """Toggle a customer's own recurring order between ACTIVE and PAUSED.
    
    When pausing (ACTIVE → PAUSED):
      - If ?cancel_upcoming=true, cancel the nearest pending generated order.
      
    When resuming (PAUSED → ACTIVE):
      - Compute the next valid recurrence date (≥48h from now) and return it.
    """
    import json
    try:
        sub = RecurringOrder.objects.get(id=sub_id, user=request.user)

        if sub.status == RecurringOrder.Status.CANCELLED:
            return JsonResponse({'error': 'Cannot toggle a cancelled subscription'}, status=400)

        response_data = {'success': True}

        if sub.status == RecurringOrder.Status.ACTIVE:
            # --- PAUSING ---
            sub.status = RecurringOrder.Status.PAUSED
            sub.save(update_fields=['status'])

            # Optionally cancel the nearest upcoming order
            body = {}
            try:
                body = json.loads(request.body) if request.body else {}
            except (json.JSONDecodeError, ValueError):
                pass

            cancelled_order_id = None
            if body.get('cancel_upcoming'):
                upcoming = sub.generated_orders.filter(
                    status=Order.Status.PENDING,
                ).order_by('order_date').first()
                if upcoming:
                    upcoming.status = Order.Status.CANCELLED
                    upcoming.save(update_fields=['status'])
                    # Also cancel any pending producer summaries for this order
                    for summary in upcoming.producer_summaries.filter(status='PEN'):
                        summary.status = 'CAN'
                        summary.save(update_fields=['status'])
                    cancelled_order_id = upcoming.id

            response_data.update({
                'new_status': sub.status,
                'new_status_display': sub.get_status_display(),
                'cancelled_order_id': cancelled_order_id,
            })

        else:
            # --- RESUMING ---
            sub.status = RecurringOrder.Status.ACTIVE
            sub.save(update_fields=['status'])

            next_date = _next_valid_recurrence_date(
                sub.recurrence_day,
                sub.recurrence_pattern,
                min_hours=48,
            )

            # Create a new pending order for the next valid delivery date
            new_order_id = None
            if next_date:
                try:
                    new_order = create_order_from_recurring_template(sub, next_date)
                    new_order_id = new_order.id
                except ValueError:
                    pass  # All products out of stock — order not created

            response_data.update({
                'new_status': sub.status,
                'new_status_display': sub.get_status_display(),
                'next_delivery_date': next_date.isoformat() if next_date else None,
                'new_order_id': new_order_id,
            })

        return JsonResponse(response_data)

    except RecurringOrder.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)


@login_required
@require_POST
def customer_cancel_subscription(request, sub_id):
    """Cancel a customer's own recurring order."""
    try:
        sub = RecurringOrder.objects.get(id=sub_id, user=request.user)

        if sub.status == RecurringOrder.Status.CANCELLED:
            return JsonResponse({'error': 'Subscription is already cancelled'}, status=400)

        sub.status = RecurringOrder.Status.CANCELLED
        sub.save(update_fields=['status'])

        # Cancel all pending generated orders
        pending_orders = sub.generated_orders.filter(status=Order.Status.PENDING)
        for order in pending_orders:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            for summary in order.producer_summaries.filter(status='PEN'):
                summary.status = 'CAN'
                summary.save(update_fields=['status'])

        return JsonResponse({'success': True})

    except RecurringOrder.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)