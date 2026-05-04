# docker compose exec web python manage.py shell
# exec(open("orders/tests/debug/debug_customer_cancellation_edge_cases.py.py").read())
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction

from orders.models import Order, ProducerOrderSummary, ProducerOrderStatusHistory
from orders.services.customer_cancellation import (
    cancel_order_as_customer,
    CustomerCancellationError,
)
from products.models import Inventory


CUSTOMER_EMAIL = "user1@gmail.com"


class RollbackDebugChanges(Exception):
    pass


User = get_user_model()


def print_result(case_id, scenario, result, details=""):
    print(f"{case_id}: {result}")
    print(f"  Scenario: {scenario}")
    if details:
        print(f"  Details: {details}")
    print("-" * 80)


def get_customer():
    return User.objects.get(email=CUSTOMER_EMAIL)


def get_wrong_customer(customer):
    return User.objects.exclude(id=customer.id).first()


def get_debug_order(customer):
    order = (
        Order.objects
        .filter(
            user=customer,
            items__isnull=False,
            producer_summaries__isnull=False,
        )
        .distinct()
        .order_by("id")
        .first()
    )

    if not order:
        raise RuntimeError(
            f"No suitable order found for {CUSTOMER_EMAIL}. "
            "Need an order with at least one item and one producer summary."
        )

    return order


def get_inventory_baseline(order):
    baseline = {}

    for item in order.items.select_related("inventory"):
        baseline[item.inventory_id] = item.inventory.remaining_quantity

    return baseline


def get_quantity_by_inventory(order):
    quantities = defaultdict(int)

    for item in order.items.all():
        quantities[item.inventory_id] += item.quantity

    return quantities


def restore_inventory(inventory_baseline):
    for inventory_id, remaining_quantity in inventory_baseline.items():
        Inventory.objects.filter(id=inventory_id).update(
            remaining_quantity=remaining_quantity
        )


def reset_order_fixture(
    *,
    order,
    inventory_baseline,
    order_status=Order.Status.PENDING,
    all_summary_status=ProducerOrderSummary.Status.PENDING,
    first_summary_status=None,
):
    Order.objects.filter(id=order.id).update(
        status=order_status,
        cancelled_at=None,
        cancelled_by_id=None,
        cancellation_reason="",
    )

    ProducerOrderSummary.objects.filter(order=order).update(
        status=all_summary_status
    )

    if first_summary_status:
        first_summary = (
            ProducerOrderSummary.objects
            .filter(order=order)
            .order_by("id")
            .first()
        )

        ProducerOrderSummary.objects.filter(id=first_summary.id).update(
            status=first_summary_status
        )

    restore_inventory(inventory_baseline)

    order.refresh_from_db()


def assert_success_state(order, customer, reason, inventory_baseline):
    order.refresh_from_db()

    summaries = list(ProducerOrderSummary.objects.filter(order=order))
    quantity_by_inventory = get_quantity_by_inventory(order)

    order_cancelled_ok = order.status == Order.Status.CANCELLED
    cancelled_at_ok = order.cancelled_at is not None
    cancelled_by_ok = order.cancelled_by_id == customer.id
    reason_ok = order.cancellation_reason == reason

    summaries_cancelled_ok = all(
        summary.status == ProducerOrderSummary.Status.CANCELLED
        for summary in summaries
    )

    stock_ok = True
    stock_details = []

    for inventory_id, original_remaining in inventory_baseline.items():
        inventory = Inventory.objects.get(id=inventory_id)
        expected_remaining = original_remaining + quantity_by_inventory[inventory_id]

        if inventory.remaining_quantity != expected_remaining:
            stock_ok = False

        stock_details.append(
            f"Inventory {inventory_id}: expected {expected_remaining}, "
            f"actual {inventory.remaining_quantity}"
        )

    history_count = ProducerOrderStatusHistory.objects.filter(
        producer_order_summary__order=order,
        new_status=ProducerOrderSummary.Status.CANCELLED,
        note=reason,
    ).count()

    history_ok = history_count == len(summaries)

    checks = {
        "order_cancelled_ok": order_cancelled_ok,
        "cancelled_at_ok": cancelled_at_ok,
        "cancelled_by_ok": cancelled_by_ok,
        "reason_ok": reason_ok,
        "summaries_cancelled_ok": summaries_cancelled_ok,
        "stock_ok": stock_ok,
        "history_ok": history_ok,
        "history_count": history_count,
        "summary_count": len(summaries),
        "stock_details": stock_details,
    }

    failed = [key for key, value in checks.items() if key.endswith("_ok") and not value]

    return failed, checks


def run_blocked_case(
    *,
    case_id,
    scenario,
    order,
    customer_to_use,
    expected_error_text,
):
    try:
        cancel_order_as_customer(
            order_id=order.id,
            customer=customer_to_use,
            reason=f"{case_id} debug reason",
        )

        print_result(
            case_id,
            scenario,
            "FAIL",
            "Cancellation was allowed, but it should have been blocked.",
        )

    except CustomerCancellationError as exc:
        message = str(exc)

        if expected_error_text in message:
            print_result(case_id, scenario, "PASS", message)
        else:
            print_result(
                case_id,
                scenario,
                "FAIL",
                f"Wrong error message. Got: {message}",
            )


def run_success_case(
    *,
    case_id,
    scenario,
    order,
    customer,
    reason,
    inventory_baseline,
):
    try:
        cancel_order_as_customer(
            order_id=order.id,
            customer=customer,
            reason=reason,
        )

        failed, checks = assert_success_state(
            order=order,
            customer=customer,
            reason=reason,
            inventory_baseline=inventory_baseline,
        )

        if failed:
            print_result(
                case_id,
                scenario,
                "FAIL",
                f"Failed checks: {failed}. Full checks: {checks}",
            )
        else:
            print_result(
                case_id,
                scenario,
                "PASS",
                (
                    f"Order cancelled, stock restored, "
                    f"{checks['history_count']} history row(s) created."
                ),
            )

    except Exception as exc:
        print_result(
            case_id,
            scenario,
            "FAIL",
            f"Unexpected exception: {type(exc).__name__}: {exc}",
        )


try:
    with transaction.atomic():
        customer = get_customer()
        wrong_customer = get_wrong_customer(customer)
        order = get_debug_order(customer)

        summaries = list(ProducerOrderSummary.objects.filter(order=order))

        if not summaries:
            raise RuntimeError("Selected order has no producer summaries.")

        inventory_baseline = get_inventory_baseline(order)

        print("=" * 80)
        print("CUSTOMER CANCELLATION EDGE CASE DEBUG")
        print("=" * 80)
        print(f"Customer: {customer.email}")
        print(f"Order used for debug: #{order.id}")
        print(f"Producer summaries: {len(summaries)}")
        print("All changes will be rolled back at the end.")
        print("=" * 80)

        # EC-001: Completed order blocked
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.COMPLETED,
        )
        run_blocked_case(
            case_id="CANCEL-EC-001",
            scenario="Customer tries to cancel a completed order",
            order=order,
            customer_to_use=customer,
            expected_error_text="Completed orders cannot be cancelled.",
        )

        # EC-002: Wrong customer blocked
        if wrong_customer:
            reset_order_fixture(
                order=order,
                inventory_baseline=inventory_baseline,
                order_status=Order.Status.PENDING,
            )
            run_blocked_case(
                case_id="CANCEL-EC-002",
                scenario="Different user tries to cancel another customer's order",
                order=order,
                customer_to_use=wrong_customer,
                expected_error_text="This order does not belong to this customer.",
            )
        else:
            print_result(
                "CANCEL-EC-002",
                "Different user tries to cancel another customer's order",
                "SKIPPED",
                "No second user exists in the database.",
            )

        # EC-003: Already cancelled order blocked
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.CANCELLED,
            all_summary_status=ProducerOrderSummary.Status.CANCELLED,
        )
        run_blocked_case(
            case_id="CANCEL-EC-003",
            scenario="Customer tries to cancel an already cancelled order",
            order=order,
            customer_to_use=customer,
            expected_error_text="This order has already been cancelled.",
        )

        # EC-004: Producer Preparing blocks cancellation
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.PENDING,
            first_summary_status=ProducerOrderSummary.Status.PREPARING,
        )
        run_blocked_case(
            case_id="CANCEL-EC-004",
            scenario="One producer summary is Preparing",
            order=order,
            customer_to_use=customer,
            expected_error_text="preparation has already started",
        )

        # EC-005: Producer Packaged blocks cancellation
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.PENDING,
            first_summary_status=ProducerOrderSummary.Status.PACKAGED,
        )
        run_blocked_case(
            case_id="CANCEL-EC-005",
            scenario="One producer summary is Packaged",
            order=order,
            customer_to_use=customer,
            expected_error_text="preparation has already started",
        )

        # EC-006: Producer Shipped blocks cancellation
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.PENDING,
            first_summary_status=ProducerOrderSummary.Status.SHIPPED,
        )
        run_blocked_case(
            case_id="CANCEL-EC-006",
            scenario="One producer summary is Shipped",
            order=order,
            customer_to_use=customer,
            expected_error_text="preparation has already started",
        )

        # EC-007: Pending order and all summaries Pending succeeds
        reason = "CANCEL-EC-007 customer cancellation debug"
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.PENDING,
            all_summary_status=ProducerOrderSummary.Status.PENDING,
        )
        run_success_case(
            case_id="CANCEL-EC-007",
            scenario="Order is Pending and all producer summaries are Pending",
            order=order,
            customer=customer,
            reason=reason,
            inventory_baseline=inventory_baseline,
        )

        # EC-008: Blank reason should default
        default_reason = "Customer requested cancellation"
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.PENDING,
            all_summary_status=ProducerOrderSummary.Status.PENDING,
        )
        run_success_case(
            case_id="CANCEL-EC-008",
            scenario="Customer submits blank cancellation reason",
            order=order,
            customer=customer,
            reason=default_reason,
            inventory_baseline=inventory_baseline,
        )

        # EC-009: Main order In Progress but summaries Pending.
        # This is a data-integrity edge case. Expected business result: blocked.
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            order_status=Order.Status.IN_PROGRESS,
            all_summary_status=ProducerOrderSummary.Status.PENDING,
        )

        try:
            cancel_order_as_customer(
                order_id=order.id,
                customer=customer,
                reason="CANCEL-EC-009 inconsistent status debug",
            )

            print_result(
                "CANCEL-EC-009",
                "Main order is In progress but all producer summaries are Pending",
                "FAIL / POSSIBLE SERVICE GAP",
                (
                    "Cancellation was allowed. Business rule says In progress "
                    "orders should use cancellation request/support flow."
                ),
            )

        except CustomerCancellationError as exc:
            print_result(
                "CANCEL-EC-009",
                "Main order is In progress but all producer summaries are Pending",
                "PASS",
                str(exc),
            )

        print("=" * 80)
        print("DEBUG COMPLETE. ROLLING BACK DATABASE CHANGES NOW.")
        print("=" * 80)

        raise RollbackDebugChanges()

except RollbackDebugChanges:
    print("Rollback complete. Database has not been permanently changed.")