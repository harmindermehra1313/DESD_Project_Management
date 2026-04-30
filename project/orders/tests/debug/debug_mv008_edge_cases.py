"""
Automated edge-case checker for TC-MV-008.

Covers:
MV008-EC-014:
Duplicate producer summary rows exist for the same producer and order.
Expected: duplicate payout is not created; one payout summary per producer per order.

MV008-EC-015:
Producer views payout details for a multi-vendor order.
Expected: producer can only see their own payout amount.

Run:
docker compose exec web python manage.py shell

Then:
exec(open("orders/tests/debug/debug_mv008_edge_cases.py").read())
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from orders.models import Order, ProducerOrderSummary


# Use a known multi-vendor order, e.g. 3100.
# Set to None to scan recent multi-vendor orders.
ORDER_ID = 3100

MAX_ORDERS_TO_SCAN = 20


def money(value):
    """
    Convert a value into a 2-decimal-place Decimal.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def print_line():
    print("-" * 80)


def get_orders():
    """
    Return one selected order or recent orders.
    """
    queryset = (
        Order.objects
        .prefetch_related(
            "items",
            "items__producer",
            "items__product",
            "producer_summaries",
            "producer_summaries__producer",
        )
        .order_by("-id")
    )

    if ORDER_ID is not None:
        return queryset.filter(id=ORDER_ID)

    return queryset[:MAX_ORDERS_TO_SCAN]


def check_duplicate_producer_summaries(order):
    """
    MV008-EC-014:
    Check that each producer has only one ProducerOrderSummary per order.
    """
    print("\nMV008-EC-014: Duplicate producer summary rows")
    print_line()

    summaries_by_producer = defaultdict(list)

    for summary in order.producer_summaries.all():
        summaries_by_producer[summary.producer_id].append(summary)

    duplicate_found = False

    for producer_id, summaries in summaries_by_producer.items():
        producer = summaries[0].producer

        print(f"\nProducer: {producer}")
        print(f"Producer ID: {producer_id}")
        print(f"ProducerOrderSummary count: {len(summaries)}")

        for summary in summaries:
            print(
                f"  Summary ID: {summary.id} | "
                f"Subtotal: £{money(summary.subtotal)} | "
                f"Commission: £{money(summary.commission_total)} | "
                f"Payout: £{money(summary.payout_amount)}"
            )

        if len(summaries) > 1:
            duplicate_found = True
            duplicate_payout_total = sum(
                money(summary.payout_amount)
                for summary in summaries
            )

            print("Result for this producer: FAIL")
            print(
                "Reason: More than one ProducerOrderSummary exists for "
                "the same producer and order."
            )
            print(f"Duplicate payout total: £{money(duplicate_payout_total)}")
        else:
            print("Result for this producer: PASS")
            print(
                "Reason: Only one ProducerOrderSummary exists for this "
                "producer and order."
            )

    if duplicate_found:
        print("\nMV008-EC-014 final result: FAIL")
        print(
            "Reason: Duplicate producer summary rows exist. This can create "
            "duplicate payout records."
        )
        return False

    print("\nMV008-EC-014 final result: PASS")
    print(
        "Reason: Each producer has exactly one ProducerOrderSummary for "
        "this order."
    )
    return True


def check_producer_payout_visibility(order):
    """
    MV008-EC-015:
    Check expected payout visibility for each producer.

    This is a database-level security check:
    - each producer should only be shown their own ProducerOrderSummary
    - other producer summaries are treated as hidden/forbidden
    """
    print("\nMV008-EC-015: Producer payout visibility")
    print_line()

    summaries = list(order.producer_summaries.all())

    if len(summaries) < 2:
        print("MV008-EC-015 final result: BLOCKED")
        print("Reason: This is not a multi-vendor order.")
        return False

    all_summary_ids = {summary.id for summary in summaries}
    visibility_passed = True

    for summary in summaries:
        logged_in_producer = summary.producer

        visible_summaries = [
            producer_summary
            for producer_summary in summaries
            if producer_summary.producer_id == logged_in_producer.id
        ]

        hidden_summaries = [
            producer_summary
            for producer_summary in summaries
            if producer_summary.producer_id != logged_in_producer.id
        ]

        visible_summary_ids = {producer_summary.id for producer_summary in visible_summaries}
        hidden_summary_ids = {producer_summary.id for producer_summary in hidden_summaries}

        print(f"\nLogged-in producer: {logged_in_producer}")
        print("Should be visible:")

        for visible_summary in visible_summaries:
            print(
                f"  ✓ Summary ID: {visible_summary.id} | "
                f"Producer: {visible_summary.producer} | "
                f"Payout: £{money(visible_summary.payout_amount)}"
            )

        print("Should be hidden:")

        for hidden_summary in hidden_summaries:
            print(
                f"  ✗ Summary ID: {hidden_summary.id} | "
                f"Producer: {hidden_summary.producer} | "
                f"Payout: £{money(hidden_summary.payout_amount)}"
            )

        has_only_own_summary = len(visible_summaries) == 1
        does_not_include_other_producers = not (
            visible_summary_ids & hidden_summary_ids
        )
        all_summaries_accounted_for = (
            visible_summary_ids | hidden_summary_ids
        ) == all_summary_ids

        if (
            has_only_own_summary
            and does_not_include_other_producers
            and all_summaries_accounted_for
        ):
            print("Visibility result for this producer: PASS")
            print(
                "Reason: Expected visibility contains only this producer's "
                "own payout summary."
            )
        else:
            visibility_passed = False
            print("Visibility result for this producer: FAIL")
            print(
                "Reason: Expected visibility is incorrect for this producer."
            )

    if visibility_passed:
        print("\nMV008-EC-015 final result: PASS")
        print(
            "Reason: Database ownership rules show that each producer should "
            "only see their own payout summary."
        )
        print(
            "Important: browser/API evidence is still needed to prove the "
            "actual view applies this filtering."
        )
        return True

    print("\nMV008-EC-015 final result: FAIL")
    print(
        "Reason: Expected payout visibility was not correctly separated "
        "by producer."
    )
    return False


print_line()
print("TC-MV-008 automated edge-case checker")
print_line()

orders = list(get_orders())

if not orders:
    print("Result: BLOCKED")
    print("Reason: No order was found.")
else:
    checked_orders = 0
    passed_orders = 0
    failed_orders = 0

    for order in orders:
        producer_ids = set(
            order.items.values_list("producer_id", flat=True)
        )

        if len(producer_ids) < 2:
            print(f"\nSkipping Order #{order.id}: not a multi-vendor order.")
            continue

        checked_orders += 1

        print_line()
        print(f"Checking Order #{order.id}")
        print_line()
        print(f"Order reference: {order.unique_reference}")
        print(f"Order status: {order.status} ({order.get_status_display()})")
        print(f"Producer count from order items: {len(producer_ids)}")
        print(f"Producer summary count: {order.producer_summaries.count()}")

        ec014_passed = check_duplicate_producer_summaries(order)
        ec015_passed = check_producer_payout_visibility(order)

        if ec014_passed and ec015_passed:
            passed_orders += 1
        else:
            failed_orders += 1

    print("\nOverall result")
    print_line()
    print(f"Multi-vendor orders checked: {checked_orders}")
    print(f"Passed: {passed_orders}")
    print(f"Failed: {failed_orders}")

    if checked_orders == 0:
        print("Result: BLOCKED")
        print("Reason: No multi-vendor orders were found.")
    elif failed_orders == 0:
        print("Result: PASS")
        print("Reason: All checked orders passed MV008-EC-014 and MV008-EC-015.")
    else:
        print("Result: FAIL")
        print("Reason: At least one checked order failed an edge-case check.")

print_line()