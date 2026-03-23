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

User = get_user_model()


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
    recurring_only: Optional[bool] = None,
) -> QuerySet[Order]:
    """
    Apply optional order history filters to an existing queryset.

    Supported filters:
    - status:
        Match the order-level status field.
    - producer_id:
        Return only orders linked to the specified producer through
        producer summaries.
    - start_date / end_date:
        Filter using the date component of order_date.
    - delivery_or_collection:
        Filter using producer summary fulfilment mode.
    - recurring_only:
        * True  -> orders created from a recurring order
        * False -> one-off orders only
        * None  -> no recurring filter

    distinct() is applied at the end because joins through related tables
    may otherwise duplicate rows.

    Args:
        queryset: Base queryset to filter.
        status: Optional order status code.
        producer_id: Optional producer primary key.
        start_date: Optional inclusive lower bound for order date.
        end_date: Optional inclusive upper bound for order date.
        delivery_or_collection: Optional fulfilment mode code.
        recurring_only: Optional recurring-order filter flag.

    Returns:
        QuerySet[Order]:
            Filtered queryset with duplicate rows removed.
    """
    if status:
        queryset = queryset.filter(status=status)

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

    if recurring_only is True:
        queryset = queryset.filter(recurring_order__isnull=False)
    elif recurring_only is False:
        queryset = queryset.filter(recurring_order__isnull=True)

    return queryset.distinct()


def get_order_history_for_user(
    *,
    user: User,
    status: Optional[str] = None,
    producer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    delivery_or_collection: Optional[str] = None,
    recurring_only: Optional[bool] = None,
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
        recurring_only=recurring_only,
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