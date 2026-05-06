"""
Debug TC-MV-012: Producer can only view their own order items.

Purpose:
Shows which order items each producer should be allowed to see for a
multi-vendor order.

Important:
This script proves the database ownership rules. The browser/manual test
is still needed to prove the actual producer page applies the same rule.

Run with:
docker compose exec web python manage.py shell

Then:
exec(open("orders/tests/debug/debug_producer_access_control.py").read())
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from orders.models import Order


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


order = (
    Order.objects
    .prefetch_related(
        "items__producer",
        "items__product",
        "producer_summaries__producer",
    )
    .filter(id=ORDER_ID)
    .first()
)

print_line()
print("TC-MV-012: Producer can only view their own order items")
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

    print("\nFull multi-vendor order contents")
    print_line()

    for producer_id, producer_items in items_by_producer.items():
        producer = producer_items[0].producer
        print(f"\nProducer: {producer}")
        print(f"Producer ID: {producer_id}")

        for item in producer_items:
            line_total = money(item.final_unit_price * item.quantity)
            print(
                f"  - Product: {item.product} | "
                f"Qty: {item.quantity} | "
                f"Unit: £{money(item.final_unit_price)} | "
                f"Line total: £{line_total}"
            )

    print("\nExpected producer visibility")
    print_line()

    all_items = set(items)

    for producer_id, visible_items in items_by_producer.items():
        producer = visible_items[0].producer
        visible_set = set(visible_items)
        forbidden_items = all_items - visible_set

        print(f"\nLogged in producer: {producer}")
        print("Should be visible:")

        for item in visible_items:
            print(f"  ✓ {item.product}")

        print("Should NOT be visible:")

        if forbidden_items:
            for item in forbidden_items:
                print(f"  ✗ {item.product} ({item.producer})")
        else:
            print("  No forbidden items because this is not a multi-vendor order.")

    print("\nProducer summary ownership check")
    print_line()

    if not summaries:
        print("Result: FAIL")
        print("Reason: No ProducerOrderSummary records found.")
    else:
        for summary in summaries:
            producer_items = items_by_producer.get(summary.producer_id, [])

            print(f"\nProducer summary ID: {summary.id}")
            print(f"Linked order ID: {summary.order_id}")
            print(f"Producer: {summary.producer}")
            print(f"Items this producer should see: {len(producer_items)}")

            if producer_items:
                print("Summary ownership result: PASS")
            else:
                print("Summary ownership result: FAIL")
                print(
                    "Reason: This producer summary does not match any "
                    "OrderItem producer in the order."
                )

    print("\nFinal database-level result")
    print_line()

    unique_producer_count = len(items_by_producer)
    summary_producer_ids = {summary.producer_id for summary in summaries}
    item_producer_ids = set(items_by_producer.keys())

    if unique_producer_count < 2:
        print("Result: BLOCKED")
        print("Reason: This is not a multi-vendor order.")
    elif item_producer_ids == summary_producer_ids:
        print("Result: PASS")
        print(
            "Reason: The database separates order items by producer and "
            "has matching producer summaries."
        )
        print(
            "Manual browser proof is still required to confirm the producer "
            "page applies this access-control rule."
        )
    else:
        print("Result: FAIL")
        print(
            "Reason: Producer summaries do not match the producers found "
            "in the order items."
        )

print_line()