"""
selectors.py

Read-only query logic for the order history feature.

Responsibilities:
- Order history fetching
- Filtering
- Order detail retrieval
- Query optimisation with related objects

Design notes:
- Selectors must remain read-only.
- Views should call selectors instead of embedding ORM logic directly.
- Filtering is always scoped to the current authenticated user's orders.
- Query optimisation is handled here with select_related() and prefetch_related().
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, QuerySet

from orders.models import Order, OrderItem, ProducerOrderSummary, ProducerOrderStatusHistory

User = get_user_model()


# Base query builders

def _get_order_history_base_queryset() -> QuerySet[Order]:
    """
    Return the base optimised queryset for order history pages.

    Optimisation strategy:
    - select_related() is used for single-valued joins from Order
    - prefetch_related() is used for reverse and multi-valued relations
    - nested producer history is prefetched for detail/history rendering
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
    Apply optional filters to an order history queryset.

    Supported filters:
    - status: order-level status
    - producer_id: only orders containing a producer summary for that producer
    - start_date / end_date: filter by order_date date component
    - delivery_or_collection: filter through producer summaries
    - recurring_only:
        * True  -> only orders generated from recurring orders
        * False -> only one-off orders
        * None  -> no filter
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


# Public selectors

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
    Return an optimised queryset of orders belonging to the given user.

    The queryset is:
    - ownership-scoped
    - ordered newest first
    - safe for use in list views / DRF list endpoints / pagination

    Example:
        get_order_history_for_user(
            user=request.user,
            status=Order.Status.COMPLETED,
            producer_id=12,
        )
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
    Return one fully optimised order belonging to the given user.

    This selector is suitable for:
    - order detail pages
    - receipt preparation
    - reorder source retrieval
    - API detail endpoints

    Raises:
        Order.DoesNotExist:
            If the order does not belong to the given user or does not exist.
    """
    return _get_order_history_base_queryset().get(pk=order_id, user=user)


def get_order_by_reference_for_user(*, user: User, unique_reference: str) -> Order:
    """
    Return one fully optimised order using the public unique reference.

    This is useful when the frontend or receipt flow uses the public
    order reference instead of the internal primary key.
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
    Convenience selector for status-specific slices of a user's orders.

    This keeps repeated view logic out of controllers when separate tabs
    or dashboard sections are needed, such as:
    - completed orders
    - cancelled orders
    - in-progress orders
    """
    return get_order_history_for_user(user=user, status=status)


def get_recent_orders_for_user(*, user: User, limit: int = 5) -> QuerySet[Order]:
    """
    Return the most recent orders for the given user.

    Useful for:
    - account dashboard widgets
    - quick reorder panels
    - homepage summaries
    """
    return get_order_history_for_user(user=user)[:limit]