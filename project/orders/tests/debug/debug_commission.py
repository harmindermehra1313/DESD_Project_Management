"""
Debug TC-MV-007: 5% commission is calculated correctly.

Purpose:
Checks whether the latest order stores total_commission as 5% of
final_total_price.

Run with:
docker compose exec web python manage.py shell

Then:
exec(open("orders/tests/debug/debug_commission.py").read())
"""

from decimal import Decimal, ROUND_HALF_UP

from orders.models import Order


COMMISSION_RATE = Decimal("0.05")
PAYOUT_RATE = Decimal("0.95")


def money(value):
    """
    Convert a value into a 2-decimal-place Decimal.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def print_line():
    print("-" * 60)


order = (
    Order.objects
    .prefetch_related("items", "producer_summaries")
    .order_by("-id")
    .first()
)

if not order:
    print("Result: BLOCKED")
    print("Reason: No orders found in the database.")
else:
    final_total = money(order.final_total_price)
    actual_order_commission = money(order.total_commission)
    expected_order_commission = money(final_total * COMMISSION_RATE)

    print_line()
    print("TC-MV-007: 5% commission is calculated correctly")
    print_line()
    print(f"Order ID: {order.id}")
    print(f"Order reference: {order.unique_reference}")
    print(f"Final total price: £{final_total}")
    print(f"Expected 5% commission: £{expected_order_commission}")
    print(f"Actual stored total_commission: £{actual_order_commission}")

    if actual_order_commission == expected_order_commission:
        print("\nOrder-level result: PASS")
        print("Reason: total_commission equals 5% of final_total_price.")
    else:
        print("\nOrder-level result: FAIL")
        print("Reason: total_commission does not equal 5% of final_total_price.")
        print(f"Expected: £{expected_order_commission}")
        print(f"Actual: £{actual_order_commission}")

    print("\nProducer summary checks")
    print_line()

    producer_summaries = list(order.producer_summaries.all())

    if not producer_summaries:
        print("No ProducerOrderSummary records found for this order.")
        print("This means producer-level commission/payout cannot be checked.")
    else:
        summary_commission_total = Decimal("0.00")
        summary_subtotal_total = Decimal("0.00")
        summary_payout_total = Decimal("0.00")

        for summary in producer_summaries:
            subtotal = money(summary.subtotal)
            actual_commission = money(summary.commission_total)
            expected_commission = money(subtotal * COMMISSION_RATE)
            actual_payout = money(summary.payout_amount)
            expected_payout = money(subtotal * PAYOUT_RATE)

            summary_commission_total += actual_commission
            summary_subtotal_total += subtotal
            summary_payout_total += actual_payout

            print(f"\nProducer: {summary.producer}")
            print(f"Subtotal: £{subtotal}")
            print(f"Expected commission: £{expected_commission}")
            print(f"Actual commission_total: £{actual_commission}")
            print(f"Expected payout: £{expected_payout}")
            print(f"Actual payout_amount: £{actual_payout}")

            if actual_commission == expected_commission:
                print("Producer commission result: PASS")
            else:
                print("Producer commission result: FAIL")

            if actual_payout == expected_payout:
                print("Producer payout result: PASS")
            else:
                print("Producer payout result: FAIL")

        print("\nOverall producer summary totals")
        print_line()
        print(f"Producer subtotal total: £{money(summary_subtotal_total)}")
        print(f"Producer commission total: £{money(summary_commission_total)}")
        print(f"Producer payout total: £{money(summary_payout_total)}")

        if money(summary_commission_total) == actual_order_commission:
            print("Summary commission total result: PASS")
            print("Reason: Producer commission totals match order total_commission.")
        else:
            print("Summary commission total result: FAIL")
            print(
                "Reason: Producer commission totals do not match "
                "order total_commission."
            )
            print(f"Expected from order: £{actual_order_commission}")
            print(f"Actual from summaries: £{money(summary_commission_total)}")

    print_line()