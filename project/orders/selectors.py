"""
orders/selectors.py

Purpose:
Centralise read-only database access for the order history feature.

This module contains selector functions responsible for retrieving order
data for authenticated users without performing any write operations.
It exists to keep ORM query construction out of views and services,
while also ensuring that related objects are loaded efficiently.

Responsibilities:
- build the base queryset used by order history and order detail flows
- apply supported order history filters
- return user-scoped order history querysets
- return a single user-scoped order by internal ID or public reference
- provide small convenience selectors for dashboards and recent activity

Architectural rules:
- selector functions must remain read-only
- user ownership must always be enforced at query level
- query optimisation belongs here, not in views
- views should call selectors instead of embedding ORM logic directly

Query optimisation strategy:
- select_related() is used for single-valued foreign key relations
- prefetch_related() is used for reverse and multi-valued relations
- nested producer status history is prefetched to reduce follow-up queries
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, QuerySet

from orders.models import Order, OrderItem, ProducerOrderSummary, ProducerOrderStatusHistory
from products.models import Inventory, Product
from django.utils import timezone

User = get_user_model()

def _normalise_derived_status_filter(value: str | None) -> str | None:
    if not value:
        return None

    normalized = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    allowed = {"pending", "in_progress", "completed"}
    return normalized if normalized in allowed else None

def _normalise_summary_status(summary: ProducerOrderSummary) -> str:
    """
    Convert one producer summary status into a stable lowercase text value.

    We prefer the display label because the uploaded files do not show the
    exact enum constant names for the producer-summary model.
    """
    try:
        display_value = summary.get_status_display()
    except Exception:
        display_value = None

    if display_value:
        return (
            str(display_value)
            .strip()
            .lower()
            .replace("-", " ")
            .replace("_", " ")
        )

    return (
        str(getattr(summary, "status", "") or "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def get_derived_order_status_key(order: Order) -> str:
    """
    Derive the public order status from producer summaries.

    Rules:
    - all Pending -> pending
    - all Shipped -> completed
    - otherwise   -> in_progress
    """
    summary_statuses = [
        _normalise_summary_status(summary)
        for summary in order.producer_summaries.all()
    ]

    if not summary_statuses:
        return "pending"

    if all(status == "pending" for status in summary_statuses):
        return "pending"

    if all(status == "shipped" for status in summary_statuses):
        return "completed"

    return "in_progress"


def get_derived_order_status_label(order: Order) -> str:
    status_key = get_derived_order_status_key(order)

    if status_key == "pending":
        return "Pending"

    if status_key == "completed":
        return "Completed"

    return "In Progress"



def _normalise_status_text(value: str | None) -> str:
    return (
        (value or "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def _normalise_requested_order_status(status: str | None) -> str | None:
    value = _normalise_status_text(status)
    if not value:
        return None

    compact = value.replace(" ", "")

    if value == "pending" or compact.startswith("pen"):
        return "pending"

    if (
        value == "completed"
        or value == "shipped"
        or compact.startswith("com")
        or compact.startswith("ship")
    ):
        return "completed"

    if (
        value == "in progress"
        or compact.startswith("inprog")
        or compact.startswith("prog")
        or compact.startswith("ipr")
    ):
        return "in_progress"

    return None


def _get_producer_summary_status_labels(order: Order) -> list[str]:
    return [
        _normalise_status_text(summary.get_status_display())
        for summary in order.producer_summaries.all()
    ]



def _get_order_history_base_queryset() -> QuerySet[Order]:
    """
    Build the shared optimised queryset for order history and order detail retrieval.

    The returned queryset loads the related objects commonly needed by:
    - order history list endpoints
    - order detail endpoints
    - receipt rendering
    - reorder flows

    Related loading plan:
    - Order.delivery_address, Order.billing_address, and Order.recurring_order
      are loaded with select_related() because each relation is single-valued.
    - Order.items is prefetched with product, inventory, and producer joins.
    - Order.producer_summaries is prefetched with producer joins.
    - ProducerOrderSummary.status_history is prefetched with updated_by joins.

    Returns:
        QuerySet[Order]:
            Base queryset ordered from newest to oldest.
    """

    item_queryset = (
        OrderItem.objects.select_related(
            "product",
            "inventory",
            "producer",
        )
        .order_by("pk")
    )

    producer_summary_queryset = (
        ProducerOrderSummary.objects.select_related("producer")
        .prefetch_related(
            Prefetch(
                "status_history",
                queryset=ProducerOrderStatusHistory.objects.select_related("updated_by").order_by("changed_at"),
            )
        )
        .order_by("pk")
    )

    return (
        Order.objects.select_related(
            "delivery_address",
            "billing_address",
            "recurring_order",
        )
        .prefetch_related(
            Prefetch("items", queryset=item_queryset),
            Prefetch("producer_summaries", queryset=producer_summary_queryset),
        )
        .order_by("-order_date", "-pk")
    )


def _apply_order_history_filters(
    queryset: QuerySet[Order],
    *,
    status: Optional[str] = None,
    producer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    delivery_or_collection: Optional[str] = None,
) -> QuerySet[Order]:
    if producer_id:
        queryset = queryset.filter(producer_summaries__producer_id=producer_id)

    if start_date:
        queryset = queryset.filter(order_date__date__gte=start_date)

    if end_date:
        queryset = queryset.filter(order_date__date__lte=end_date)

    if delivery_or_collection:
        queryset = queryset.filter(
            producer_summaries__delivery_or_collection=delivery_or_collection
        )

    queryset = queryset.distinct()

    derived_status = _normalise_derived_status_filter(status)
    if status and derived_status is None:
        return queryset.none()

    if derived_status:
        matching_ids = [
            order.pk
            for order in queryset
            if get_derived_order_status_key(order) == derived_status
        ]
        queryset = queryset.filter(pk__in=matching_ids)

    return queryset

def get_order_history_for_user(
    *,
    user: User,
    status: Optional[str] = None,
    producer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    delivery_or_collection: Optional[str] = None,
) -> QuerySet[Order]:
    """
    Return an optimised order history queryset scoped to one authenticated user.

    This selector is intended for list-style consumers such as:
    - paginated API endpoints
    - account history pages
    - filtered dashboard views

    Behaviour:
    - restricts results to orders owned by the supplied user
    - applies optional filters
    - preserves newest-first ordering from the base queryset

    Args:
        user: Authenticated user whose orders should be returned.
        status: Optional order status code.
        producer_id: Optional producer primary key.
        start_date: Optional inclusive lower bound for order date.
        end_date: Optional inclusive upper bound for order date.
        delivery_or_collection: Optional fulfilment mode code.
        recurring_only: Optional recurring-order filter flag.

    Returns:
        QuerySet[Order]:
            Optimised, user-scoped queryset ready for list views or pagination.
    """
    queryset = _get_order_history_base_queryset().filter(user=user)

    return _apply_order_history_filters(
        queryset,
        status=status,
        producer_id=producer_id,
        start_date=start_date,
        end_date=end_date,
        delivery_or_collection=delivery_or_collection,
    )


def get_order_detail_for_user(*, user: User, order_id: int) -> Order:
    """
    Return one fully optimised order belonging to the supplied user.

    This selector is suitable for:
    - order detail pages
    - receipt generation
    - reorder source lookup
    - API detail endpoints

    Security rule:
    - both the primary key and the user ownership condition are enforced
      in the query itself

    Args:
        user: Authenticated owner of the order.
        order_id: Internal primary key of the order.

    Returns:
        Order:
            Matching order instance with related objects already loaded.

    Raises:
        Order.DoesNotExist:
            Raised when the order does not exist or does not belong to the user.
    """
    return _get_order_history_base_queryset().get(pk=order_id, user=user)


def get_order_by_reference_for_user(*, user: User, unique_reference: str) -> Order:
    """
    Return one fully optimised order using its public reference value.

    This selector is useful when the external interface uses a public
    order reference instead of an internal database primary key.

    Args:
        user: Authenticated owner of the order.
        unique_reference: Public-facing order reference.

    Returns:
        Order:
            Matching order instance with related objects already loaded.

    Raises:
        Order.DoesNotExist:
            Raised when the order does not exist or does not belong to the user.
    """
    return _get_order_history_base_queryset().get(
        unique_reference=unique_reference,
        user=user,
    )


def get_orders_for_status_dashboard(
    *,
    user: User,
    status: str,
) -> QuerySet[Order]:
    """
    Return a status-specific slice of a user's order history.

    This function exists as a small convenience wrapper for dashboard
    sections or tabs that repeatedly request the same filtered subset,
    for example:
    - completed orders
    - cancelled orders
    - in-progress orders

    Args:
        user: Authenticated user whose orders should be returned.
        status: Order status code to filter by.

    Returns:
        QuerySet[Order]:
            Optimised user-scoped queryset filtered by status.
    """
    return get_order_history_for_user(user=user, status=status)


def get_recent_orders_for_user(*, user: User, limit: int = 5) -> QuerySet[Order]:
    """
    Return a limited slice of the most recent orders for one user.

    Typical use cases:
    - account dashboard widgets
    - quick reorder panels
    - homepage order summaries

    Args:
        user: Authenticated user whose recent orders should be returned.
        limit: Maximum number of records to return.

    Returns:
        QuerySet[Order]:
            Slice of the newest orders for the user.
    """
    return get_order_history_for_user(user=user)[:limit]
def get_reorder_suggestion_inventories(
    *,
    source_product: Product,
    original_producer_id: int,
    limit: int = 3,
) -> list[Inventory]:
    """
    Return alternative inventory batches for reorder suggestions.

    Matching rules:
    - prefer the same product type when the source product has one
    - otherwise fall back to the broader category
    - only include products from a different producer
    - only include published, available products with live stock
    - only include non-expired inventory batches
    - exclude the original product itself

    The function returns inventory batches rather than product rows so the
    caller can price the suggestion using the live inventory context.
    """
    today = timezone.localdate()

    queryset = (
        Inventory.objects.select_related(
            "product",
            "product__producer",
            "product__category",
            "product__product_type",
        )
        .filter(
            remaining_quantity__gt=0,
            expiry_date__gte=today,
            product__status=Product.Status.PUBLISHED,
            product__availability_status=Product.Availability_status.AVAILABLE,
        )
        .exclude(product_id=source_product.pk)
        .exclude(product__producer_id=original_producer_id)
        .order_by("expiry_date", "product__name", "pk")
    )

    if getattr(source_product, "product_type_id", None):
        queryset = queryset.filter(product__product_type_id=source_product.product_type_id)
    elif getattr(source_product, "category_id", None):
        queryset = queryset.filter(product__category_id=source_product.category_id)
    else:
        return []

    suggestions: list[Inventory] = []
    seen_product_ids: set[int] = set()

    for inventory in queryset:
        if inventory.product_id in seen_product_ids:
            continue

        suggestions.append(inventory)
        seen_product_ids.add(inventory.product_id)

        if len(suggestions) >= limit:
            break

    return suggestions