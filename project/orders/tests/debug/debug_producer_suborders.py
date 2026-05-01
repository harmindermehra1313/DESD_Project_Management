"""
Debug TC-MV-011: Producer sub-orders are created and linked.

Purpose:
Checks whether a completed multi-vendor order has one ProducerOrderSummary
for each producer in the order items.

Run with:
docker compose exec web python manage.py shell

Then:
exec(open("orders/tests/debug/debug_producer_suborders.py").read())
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from orders.models import Order


# Use the known multi-vendor order from the previous debug output.
# Set this to None to check the latest order instead.
ORDER_ID = 3100


def money(value):
    """
    Convert a value into a 2-decimal-place Decimal.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def print_line():
    print("-" * 70)


if ORDER_ID is None:
    order = (
        Order.objects
        .prefetch_related("items__producer", "items__product", "producer_summaries__producer")
        .order_by("-id")
        .first()
    )
else:
    order = (
        Order.objects
        .prefetch_related("items__producer", "items__product", "producer_summaries__producer")
        .filter(id=ORDER_ID)
        .first()
    )


print_line()
print("TC-MV-011: Producer sub-orders are created and linked")
print_line()

if not order:
    print("Result: BLOCKED")
    print(f"Reason: Order {ORDER_ID} was not found.")
else:
    print(f"Main order ID: {order.id}")
    print(f"Order reference: {order.unique_reference}")
    print(f"Order status: {order.get_status_display()}")
    print(f"Final total price: £{money(order.final_total_price)}")

    items = list(order.items.all())
    summaries = list(order.producer_summaries.all())

    items_by_producer = defaultdict(list)

    for item in items:
        items_by_producer[item.producer_id].append(item)

    item_producer_ids = set(items_by_producer.keys())
    summary_producer_ids = {summary.producer_id for summary in summaries}

    print("\nOrder item producer groups")
    print_line()

    if not items:
        print("No order items found.")
    else:
        for producer_id, producer_items in items_by_producer.items():
            producer = producer_items[0].producer
            print(f"\nProducer: {producer}")
            print(f"Producer ID: {producer_id}")
            print(f"Item count: {len(producer_items)}")

            for item in producer_items:
                line_total = money(item.final_unit_price * item.quantity)
                print(
                    f"  - {item.product} | "
                    f"Qty: {item.quantity} | "
                    f"Unit: £{money(item.final_unit_price)} | "
                    f"Line total: £{line_total}"
                )

    print("\nProducerOrderSummary records")
    print_line()

    if not summaries:
        print("No ProducerOrderSummary records found.")
    else:
        for summary in summaries:
            print(f"\nSummary ID: {summary.id}")
            print(f"Linked order ID: {summary.order_id}")
            print(f"Producer: {summary.producer}")
            print(f"Producer ID: {summary.producer_id}")
            print(f"Subtotal: £{money(summary.subtotal)}")
            print(f"Commission total: £{money(summary.commission_total)}")
            print(f"Payout amount: £{money(summary.payout_amount)}")
            print(f"Delivery date: {summary.delivery_date}")
            print(f"Delivery/collection: {summary.get_delivery_or_collection_display()}")
            print(f"Status: {summary.get_status_display()}")

    print("\nValidation")
    print_line()

    expected_summary_count = len(item_producer_ids)
    actual_summary_count = len(summaries)

    print(f"Unique producers in order items: {expected_summary_count}")
    print(f"ProducerOrderSummary records linked to order: {actual_summary_count}")

    missing_summary_producers = item_producer_ids - summary_producer_ids
    extra_summary_producers = summary_producer_ids - item_producer_ids

    has_correct_count = expected_summary_count == actual_summary_count
    has_matching_producers = not missing_summary_producers and not extra_summary_producers
    all_summaries_linked_to_order = all(
        summary.order_id == order.id for summary in summaries
    )

    if has_correct_count:
        print("Summary count result: PASS")
    else:
        print("Summary count result: FAIL")

    if has_matching_producers:
        print("Producer matching result: PASS")
    else:
        print("Producer matching result: FAIL")

        if missing_summary_producers:
            print(f"Missing summary producer IDs: {sorted(missing_summary_producers)}")

        if extra_summary_producers:
            print(f"Extra summary producer IDs: {sorted(extra_summary_producers)}")

    if all_summaries_linked_to_order:
        print("Order link result: PASS")
    else:
        print("Order link result: FAIL")
        print("Reason: At least one ProducerOrderSummary is not linked to this order.")

    print("\nFinal result")
    print_line()

    if items and summaries and has_correct_count and has_matching_producers and all_summaries_linked_to_order:
        print("Result: PASS")
        print(
            "Reason: The order has one linked ProducerOrderSummary for each "
            "producer found in the order items."
        )
    else:
        print("Result: FAIL")
        print(
            "Reason: Producer sub-orders are missing, duplicated, incorrectly "
            "linked, or do not match the producers in the order items."
        )

print_line()