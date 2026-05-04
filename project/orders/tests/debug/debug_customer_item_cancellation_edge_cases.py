# docker compose exec web python manage.py shell
# exec(open("orders/tests/debug/debug_customer_item_cancellation_edge_cases.py").read())

from django.contrib.auth import get_user_model
from django.db import transaction

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
)
from orders.services.customer_item_cancellation import (
    CustomerItemCancellationError,
    cancel_order_item_as_customer,
)
from orders.services.order_status import get_order_status_context
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


def get_target_item(order):
    item = (
        OrderItem.objects
        .filter(order=order)
        .select_related("inventory", "producer")
        .order_by("id")
        .first()
    )

    if not item:
        raise RuntimeError("Selected order has no order items.")

    return item


def get_inventory_baseline(order):
    baseline = {}

    for item in order.items.select_related("inventory"):
        baseline[item.inventory_id] = item.inventory.remaining_quantity

    return baseline


def get_item_quantity_baseline(order):
    return {
        item.id: item.quantity
        for item in order.items.all()
    }


def restore_inventory(inventory_baseline):
    for inventory_id, remaining_quantity in inventory_baseline.items():
        Inventory.objects.filter(id=inventory_id).update(
            remaining_quantity=remaining_quantity
        )


def restore_item_quantities(item_quantity_baseline):
    for item_id, quantity in item_quantity_baseline.items():
        OrderItem.objects.filter(id=item_id).update(quantity=quantity)


def get_summary_for_item(order, item):
    return (
        ProducerOrderSummary.objects
        .filter(order=order, producer_id=item.producer_id)
        .order_by("id")
        .first()
    )


def reset_order_fixture(
    *,
    order,
    inventory_baseline,
    item_quantity_baseline,
    order_status=Order.Status.PENDING,
    all_summary_status=ProducerOrderSummary.Status.PENDING,
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

    OrderItem.objects.filter(order=order).update(
        status=OrderItem.Status.ACTIVE,
        cancelled_quantity=0,
        cancelled_at=None,
        cancelled_by_id=None,
        cancellation_reason="",
    )

    restore_item_quantities(item_quantity_baseline)
    restore_inventory(inventory_baseline)

    order.refresh_from_db()


def assert_inventory_remaining(inventory_id, expected_remaining):
    actual_remaining = Inventory.objects.get(id=inventory_id).remaining_quantity

    if actual_remaining != expected_remaining:
        return (
            False,
            f"Inventory {inventory_id}: expected {expected_remaining}, actual {actual_remaining}",
        )

    return (
        True,
        f"Inventory {inventory_id}: expected {expected_remaining}, actual {actual_remaining}",
    )


def run_blocked_case(
    *,
    case_id,
    scenario,
    order,
    item,
    customer_to_use,
    expected_error_text,
):
    try:
        cancel_order_item_as_customer(
            order_id=order.id,
            order_item_id=item.id,
            customer=customer_to_use,
            reason=f"{case_id} debug reason",
        )

        print_result(
            case_id,
            scenario,
            "FAIL",
            "Cancellation was allowed, but it should have been blocked.",
        )

    except CustomerItemCancellationError as exc:
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


def run_whole_item_success_case(
    *,
    case_id,
    scenario,
    order,
    target_item,
    customer,
    inventory_baseline,
    forced_quantity,
):
    OrderItem.objects.filter(id=target_item.id).update(
        quantity=forced_quantity,
        status=OrderItem.Status.ACTIVE,
        cancelled_quantity=0,
        cancelled_at=None,
        cancelled_by_id=None,
        cancellation_reason="",
    )

    target_item.refresh_from_db()
    summary = get_summary_for_item(order, target_item)

    producer_item_count = OrderItem.objects.filter(
        order=order,
        producer_id=target_item.producer_id,
    ).count()

    history_before = ProducerOrderStatusHistory.objects.filter(
        producer_order_summary=summary,
        new_status=ProducerOrderSummary.Status.CANCELLED,
    ).count()

    expected_stock = inventory_baseline[target_item.inventory_id] + forced_quantity

    try:
        result = cancel_order_item_as_customer(
            order_id=order.id,
            order_item_id=target_item.id,
            customer=customer,
            reason=f"{case_id} whole item cancellation debug",
        )

        item = result["item"]
        item.refresh_from_db()
        summary.refresh_from_db()
        order.refresh_from_db()

        stock_ok, stock_details = assert_inventory_remaining(
            target_item.inventory_id,
            expected_stock,
        )

        item_ok = (
            item.status == OrderItem.Status.CANCELLED
            and item.cancelled_quantity == forced_quantity
            and item.active_quantity == 0
            and item.cancelled_by_id == customer.id
        )

        expected_summary_status = (
            ProducerOrderSummary.Status.CANCELLED
            if producer_item_count == 1
            else ProducerOrderSummary.Status.PENDING
        )

        summary_ok = summary.status == expected_summary_status

        history_after = ProducerOrderStatusHistory.objects.filter(
            producer_order_summary=summary,
            new_status=ProducerOrderSummary.Status.CANCELLED,
        ).count()

        history_ok = True
        if expected_summary_status == ProducerOrderSummary.Status.CANCELLED:
            history_ok = history_after == history_before + 1

        status_context = get_order_status_context(order)

        if item_ok and stock_ok and summary_ok and history_ok:
            print_result(
                case_id,
                scenario,
                "PASS",
                (
                    f"Whole item cancelled. Quantity: {forced_quantity}. "
                    f"{stock_details}. Producer summary status: {summary.status}. "
                    f"Order status context: {status_context}"
                ),
            )
        else:
            print_result(
                case_id,
                scenario,
                "FAIL",
                (
                    f"item_ok={item_ok}, stock_ok={stock_ok}, "
                    f"summary_ok={summary_ok}, history_ok={history_ok}, "
                    f"item_status={item.status}, "
                    f"cancelled_quantity={item.cancelled_quantity}, "
                    f"active_quantity={item.active_quantity}, "
                    f"summary_status={summary.status}, "
                    f"expected_summary_status={expected_summary_status}, "
                    f"{stock_details}, "
                    f"status_context={status_context}"
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
        target_item = get_target_item(order)

        inventory_baseline = get_inventory_baseline(order)
        item_quantity_baseline = get_item_quantity_baseline(order)

        print("=" * 80)
        print("CUSTOMER ITEM CANCELLATION EDGE CASE DEBUG")
        print("=" * 80)
        print(f"Customer: {customer.email}")
        print(f"Order used for debug: #{order.id}")
        print(f"Target item: #{target_item.id}")
        print(f"Target product: {target_item.product}")
        print(f"Target producer: {target_item.producer}")
        print("Rule: item cancellation cancels the whole OrderItem row.")
        print("All database changes will be rolled back at the end.")
        print("=" * 80)

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-001: Whole item cancellation succeeds when quantity == 1
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()

        run_whole_item_success_case(
            case_id="ITEM-CANCEL-EC-001",
            scenario="Customer cancels an item where quantity is 1",
            order=order,
            target_item=target_item,
            customer=customer,
            inventory_baseline=inventory_baseline,
            forced_quantity=1,
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-002: Whole item cancellation succeeds when quantity > 1
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()

        run_whole_item_success_case(
            case_id="ITEM-CANCEL-EC-002",
            scenario="Customer cancels an item where quantity is greater than 1",
            order=order,
            target_item=target_item,
            customer=customer,
            inventory_baseline=inventory_baseline,
            forced_quantity=5,
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-003: Wrong customer blocked
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()

        if wrong_customer:
            run_blocked_case(
                case_id="ITEM-CANCEL-EC-003",
                scenario="Different customer tries to cancel another customer's item",
                order=order,
                item=target_item,
                customer_to_use=wrong_customer,
                expected_error_text="This order does not belong to this customer.",
            )
        else:
            print_result(
                "ITEM-CANCEL-EC-003",
                "Different customer tries to cancel another customer's item",
                "SKIPPED",
                "No second user exists in the database.",
            )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-004: Completed order blocked
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
            order_status=Order.Status.COMPLETED,
        )

        target_item.refresh_from_db()

        run_blocked_case(
            case_id="ITEM-CANCEL-EC-004",
            scenario="Customer tries to cancel an item from a completed order",
            order=order,
            item=target_item,
            customer_to_use=customer,
            expected_error_text="Completed orders cannot be cancelled",
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-005: Cancelled order blocked
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
            order_status=Order.Status.CANCELLED,
        )

        target_item.refresh_from_db()

        run_blocked_case(
            case_id="ITEM-CANCEL-EC-005",
            scenario="Customer tries to cancel an item from an already cancelled order",
            order=order,
            item=target_item,
            customer_to_use=customer,
            expected_error_text="This order has already been cancelled.",
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-006: Producer already preparing blocks item cancellation
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()
        summary = get_summary_for_item(order, target_item)

        ProducerOrderSummary.objects.filter(id=summary.id).update(
            status=ProducerOrderSummary.Status.PREPARING
        )

        run_blocked_case(
            case_id="ITEM-CANCEL-EC-006",
            scenario="Customer tries to cancel an item after producer starts preparing",
            order=order,
            item=target_item,
            customer_to_use=customer,
            expected_error_text="producer has already started preparing",
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-007: Already cancelled item blocked
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()

        OrderItem.objects.filter(id=target_item.id).update(
            status=OrderItem.Status.CANCELLED,
            cancelled_quantity=target_item.quantity,
        )

        target_item.refresh_from_db()

        run_blocked_case(
            case_id="ITEM-CANCEL-EC-007",
            scenario="Customer tries to cancel an already cancelled item",
            order=order,
            item=target_item,
            customer_to_use=customer,
            expected_error_text="This item has already been cancelled.",
        )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-008: Cancelling last active item for a producer cancels producer summary
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()
        summary = get_summary_for_item(order, target_item)

        other_items_same_producer = (
            OrderItem.objects
            .filter(order=order, producer_id=target_item.producer_id)
            .exclude(id=target_item.id)
        )

        for other_item in other_items_same_producer:
            OrderItem.objects.filter(id=other_item.id).update(
                status=OrderItem.Status.CANCELLED,
                cancelled_quantity=other_item.quantity,
            )

        history_before = ProducerOrderStatusHistory.objects.filter(
            producer_order_summary=summary,
            new_status=ProducerOrderSummary.Status.CANCELLED,
        ).count()

        try:
            result = cancel_order_item_as_customer(
                order_id=order.id,
                order_item_id=target_item.id,
                customer=customer,
                reason="ITEM-CANCEL-EC-008 last producer item cancellation debug",
            )

            summary.refresh_from_db()
            order.refresh_from_db()

            history_after = ProducerOrderStatusHistory.objects.filter(
                producer_order_summary=summary,
                new_status=ProducerOrderSummary.Status.CANCELLED,
            ).count()

            summary_ok = summary.status == ProducerOrderSummary.Status.CANCELLED
            history_ok = history_after == history_before + 1

            if summary_ok and history_ok:
                print_result(
                    "ITEM-CANCEL-EC-008",
                    "Customer cancels the last active item for one producer",
                    "PASS",
                    (
                        f"Producer summary cancelled. "
                        f"Order status context: {get_order_status_context(order)}"
                    ),
                )
            else:
                print_result(
                    "ITEM-CANCEL-EC-008",
                    "Customer cancels the last active item for one producer",
                    "FAIL",
                    (
                        f"summary_ok={summary_ok}, history_ok={history_ok}, "
                        f"summary_status={summary.status}, "
                        f"history_before={history_before}, history_after={history_after}"
                    ),
                )

        except Exception as exc:
            print_result(
                "ITEM-CANCEL-EC-008",
                "Customer cancels the last active item for one producer",
                "FAIL",
                f"Unexpected exception: {type(exc).__name__}: {exc}",
            )

        # ------------------------------------------------------------------
        # ITEM-CANCEL-EC-009: Cancelling only remaining active item in order cancels whole order
        # ------------------------------------------------------------------
        reset_order_fixture(
            order=order,
            inventory_baseline=inventory_baseline,
            item_quantity_baseline=item_quantity_baseline,
        )

        target_item.refresh_from_db()
        target_summary = get_summary_for_item(order, target_item)

        # Pretend all other items and producer summaries are already cancelled.
        for other_item in OrderItem.objects.filter(order=order).exclude(id=target_item.id):
            OrderItem.objects.filter(id=other_item.id).update(
                status=OrderItem.Status.CANCELLED,
                cancelled_quantity=other_item.quantity,
            )

        ProducerOrderSummary.objects.filter(order=order).exclude(
            id=target_summary.id
        ).update(status=ProducerOrderSummary.Status.CANCELLED)

        try:
            result = cancel_order_item_as_customer(
                order_id=order.id,
                order_item_id=target_item.id,
                customer=customer,
                reason="ITEM-CANCEL-EC-009 final active item cancellation debug",
            )

            order.refresh_from_db()
            target_summary.refresh_from_db()

            status_context = get_order_status_context(order)

            order_ok = order.status == Order.Status.CANCELLED
            summary_ok = target_summary.status == ProducerOrderSummary.Status.CANCELLED
            status_context_ok = status_context["status_key"] == "cancelled"

            if order_ok and summary_ok and status_context_ok:
                print_result(
                    "ITEM-CANCEL-EC-009",
                    "Customer cancels the only remaining active item in the order",
                    "PASS",
                    (
                        f"Whole order became Cancelled. "
                        f"Order status context: {status_context}"
                    ),
                )
            else:
                print_result(
                    "ITEM-CANCEL-EC-009",
                    "Customer cancels the only remaining active item in the order",
                    "FAIL",
                    (
                        f"order_ok={order_ok}, summary_ok={summary_ok}, "
                        f"status_context_ok={status_context_ok}, "
                        f"order_status={order.status}, "
                        f"summary_status={target_summary.status}, "
                        f"status_context={status_context}"
                    ),
                )

        except Exception as exc:
            print_result(
                "ITEM-CANCEL-EC-009",
                "Customer cancels the only remaining active item in the order",
                "FAIL",
                f"Unexpected exception: {type(exc).__name__}: {exc}",
            )

        print("=" * 80)
        print("DEBUG COMPLETE. ROLLING BACK DATABASE CHANGES NOW.")
        print("=" * 80)

        raise RollbackDebugChanges()

except RollbackDebugChanges:
    print("Rollback complete. Database has not been permanently changed.")