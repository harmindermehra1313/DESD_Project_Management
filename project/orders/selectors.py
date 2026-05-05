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
- return live reorder suggestion inventories

Architectural rules:
- selector functions must remain read-only
- user ownership must always be enforced at query level
- query optimisation belongs here, not in views
- views and services should call selectors instead of embedding ORM logic directly

Query optimisation strategy:
- select_related() is used for single-valued foreign key relations
- prefetch_related() is used for reverse and multi-valued relations
- nested producer status history is prefetched to reduce follow-up queries
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery, Sum
from django.utils import timezone

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
)
from orders.services.order_status import get_order_status_context
from products.models import Inventory, Product

User = get_user_model()

TRENDING_RANK_LIMIT = 10
TRENDING_LOOKBACK_DAYS = 30
TRENDING_MIN_COMPLETED_ORDERS = 2
NEW_PRODUCT_LOOKBACK_DAYS = 14


ORDER_STATUS_FILTER_ALIASES = {
    "pending": "pending",
    "pen": "pending",
    "in_progress": "in_progress",
    "inprogress": "in_progress",
    "progress": "in_progress",
    "ipr": "in_progress",
    "packaged": "packaged",
    "package": "packaged",
    "ready_for_collection": "ready_for_collection",
    "readyforcollection": "ready_for_collection",
    "collection_ready": "ready_for_collection",
    "completed": "completed",
    "complete": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "cancel": "cancelled",
}


def _normalise_filter_text(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalise_derived_status_filter(value: str | None) -> str | None:
    """
    Convert a request status filter into the stable customer-facing status key.

    The returned value must match get_order_status_context(order)["status_key"].
    """
    normalised = _normalise_filter_text(value)

    if not normalised:
        return None

    return ORDER_STATUS_FILTER_ALIASES.get(normalised)


def get_derived_order_status_key(order: Order) -> str:
    """
    Return the customer-facing order status key.

    Status derivation is delegated to orders.services.order_status so that:
    - the order history filter
    - order history serializer
    - order detail serializer
    - parent order status sync workflow

    all use the same rules.
    """
    return get_order_status_context(order)["status_key"]


def get_derived_order_status_label(order: Order) -> str:
    """
    Return the customer-facing order status display label.
    """
    return get_order_status_context(order)["status_display"]


def _get_order_history_base_queryset() -> QuerySet[Order]:
    """
    Build the shared optimised queryset for order history and order detail retrieval.

    The returned queryset loads the related objects commonly needed by:
    - order history list endpoints
    - order detail endpoints
    - receipt rendering
    - reorder flows

    Returns:
        QuerySet[Order]:
            Base queryset ordered from newest to oldest.
    """
    item_queryset = OrderItem.objects.select_related(
        "product",
        "inventory",
        "producer",
    ).order_by("pk")

    producer_summary_queryset = (
        ProducerOrderSummary.objects.select_related("producer")
        .prefetch_related(
            Prefetch(
                "status_history",
                queryset=ProducerOrderStatusHistory.objects.select_related(
                    "updated_by"
                ).order_by("changed_at"),
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
    """
    Apply order history filters.

    Status filtering is handled after basic database filters because the
    customer-facing status is derived from producer summaries and cancellation
    state rather than only one simple database field.
    """
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
    """
    return _get_order_history_base_queryset().get(pk=order_id, user=user)


def get_order_by_reference_for_user(*, user: User, unique_reference: str) -> Order:
    """
    Return one fully optimised order using its public reference value.
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
    """
    return get_order_history_for_user(user=user, status=status)


def get_recent_orders_for_user(*, user: User, limit: int = 5) -> QuerySet[Order]:
    """
    Return a limited slice of the most recent orders for one user.
    """
    return get_order_history_for_user(user=user)[:limit]


def _build_live_product_queryset(
    *,
    preferred_inventory_subquery: Subquery,
) -> QuerySet[Product]:
    """
    Return live products that have at least one sellable inventory batch.

    A product is considered live for reorder suggestions when:
    - product is published
    - product is not discontinued
    - at least one active inventory batch has remaining stock
    - the preferred batch has not expired
    """
    return (
        Product.objects.select_related(
            "producer",
            "category",
            "product_type",
        )
        .filter(
            status=Product.Status.PUBLISHED,
        )
        .exclude(
            availability_status=Product.Availability_status.DISCONTINUED,
        )
        .annotate(
            preferred_inventory_id=Subquery(preferred_inventory_subquery),
        )
        .filter(preferred_inventory_id__isnull=False)
    )


def _get_top_trending_product_ids(
    *,
    product_queryset: QuerySet[Product],
    recent_completed_order_filter: Q,
) -> set[int]:
    """
    Return true top-ranked product IDs inside the supplied type/category scope.

    Important:
    - this queryset should not exclude products from the original order
    - the result is used only to decide whether a candidate deserves the
      Trending badge
    """
    return set(
        product_queryset.annotate(
            recent_completed_order_count=Count(
                "order_items",
                filter=recent_completed_order_filter,
            ),
            recent_quantity_sold=Sum(
                "order_items__quantity",
                filter=recent_completed_order_filter,
            ),
        )
        .filter(
            recent_completed_order_count__gte=TRENDING_MIN_COMPLETED_ORDERS,
        )
        .order_by(
            "-recent_completed_order_count",
            "-recent_quantity_sold",
            "name",
            "pk",
        )
        .values_list("pk", flat=True)[:TRENDING_RANK_LIMIT]
    )


def get_reorder_suggestion_inventories(
    *,
    source_product: Product,
    original_producer_id: int,
    limit: int = 3,
    excluded_product_ids: set[int] | None = None,
) -> list[Inventory]:
    """
    Return live reorder suggestions for one historical order item.

    Recommendation rule:
    - prefer the same product type
    - fall back to the same category when no same-type suggestions exist
    - exclude products already bought in the same original order
    - return up to two popular live products
    - return one discovery product where possible
    - show Trending only when the product is truly in the top 10 for that scope
    - show New only when the product was added recently
    - use Inventory as the source of truth for live stock

    Important:
    - the original product is excluded
    - other products from the same original order can also be excluded by
      passing excluded_product_ids
    - the original producer is not excluded because suggestions are across
      all producers
    """
    if limit <= 0:
        return []

    _ = original_producer_id

    today = timezone.localdate()
    trending_cutoff = timezone.now() - timedelta(days=TRENDING_LOOKBACK_DAYS)
    new_product_cutoff = timezone.now() - timedelta(days=NEW_PRODUCT_LOOKBACK_DAYS)

    preferred_inventory_subquery = (
        Inventory.objects.filter(
            product_id=OuterRef("pk"),
            status=Inventory.BatchStatus.ACTIVE,
            remaining_quantity__gt=0,
            expiry_date__gte=today,
        )
        .order_by("expiry_date", "created_at", "pk")
        .values("pk")[:1]
    )

    live_product_queryset = _build_live_product_queryset(
        preferred_inventory_subquery=preferred_inventory_subquery,
    )

    excluded_product_ids = set(excluded_product_ids or set())
    excluded_product_ids.add(source_product.pk)

    candidate_queryset = live_product_queryset.exclude(pk__in=excluded_product_ids)

    completed_order_filter = Q(order_items__order__status=Order.Status.COMPLETED)

    recent_completed_order_filter = Q(
        order_items__order__status=Order.Status.COMPLETED,
        order_items__order__order_date__gte=trending_cutoff,
    )

    def is_recent_product(product: Product) -> bool:
        created_at = getattr(product, "created_at", None)
        return bool(created_at and created_at >= new_product_cutoff)

    def select_products(
        *,
        candidates: QuerySet[Product],
        ranking_scope: QuerySet[Product],
    ) -> list[Product]:
        selected_products: list[Product] = []

        top_trending_product_ids = _get_top_trending_product_ids(
            product_queryset=ranking_scope,
            recent_completed_order_filter=recent_completed_order_filter,
        )

        popular_products = list(
            candidates.annotate(
                completed_order_count=Count(
                    "order_items",
                    filter=completed_order_filter,
                ),
                total_quantity_sold=Sum(
                    "order_items__quantity",
                    filter=completed_order_filter,
                ),
            )
            .filter(completed_order_count__gt=0)
            .order_by(
                "-completed_order_count",
                "-total_quantity_sold",
                "name",
                "pk",
            )[: min(2, limit)]
        )

        for product in popular_products:
            if product.pk in top_trending_product_ids:
                product.reorder_recommendation_badge = "trending"

        selected_products.extend(popular_products)
        selected_product_ids = [product.pk for product in selected_products]

        if len(selected_products) < limit:
            discovery_product = (
                candidates.exclude(pk__in=selected_product_ids)
                .annotate(
                    completed_order_count=Count(
                        "order_items",
                        filter=completed_order_filter,
                    )
                )
                .filter(completed_order_count=0)
                .order_by("-created_at", "name", "pk")
                .first()
            )

            if discovery_product is None:
                discovery_product = (
                    candidates.exclude(pk__in=selected_product_ids)
                    .order_by("-created_at", "name", "pk")
                    .first()
                )

            if discovery_product is not None:
                if is_recent_product(discovery_product):
                    discovery_product.reorder_recommendation_badge = "new"

                selected_products.append(discovery_product)
                selected_product_ids.append(discovery_product.pk)

        if len(selected_products) < limit:
            fallback_products = list(
                candidates.exclude(pk__in=selected_product_ids)
                .order_by("-created_at", "name", "pk")[
                    : limit - len(selected_products)
                ]
            )

            selected_products.extend(fallback_products)

        return selected_products[:limit]

    scoped_querysets: list[tuple[QuerySet[Product], QuerySet[Product]]] = []

    if getattr(source_product, "product_type_id", None):
        scoped_querysets.append(
            (
                candidate_queryset.filter(product_type_id=source_product.product_type_id),
                live_product_queryset.filter(
                    product_type_id=source_product.product_type_id
                ),
            )
        )

    if getattr(source_product, "category_id", None):
        scoped_querysets.append(
            (
                candidate_queryset.filter(category_id=source_product.category_id),
                live_product_queryset.filter(category_id=source_product.category_id),
            )
        )

    selected_products: list[Product] = []

    for candidates, ranking_scope in scoped_querysets:
        selected_products = select_products(
            candidates=candidates,
            ranking_scope=ranking_scope,
        )

        if selected_products:
            break

    if not selected_products:
        return []

    inventory_ids = [
        product.preferred_inventory_id
        for product in selected_products
        if product.preferred_inventory_id
    ]

    inventories_by_id = {
        inventory.pk: inventory
        for inventory in Inventory.objects.select_related(
            "product",
            "product__producer",
            "product__category",
            "product__product_type",
        ).filter(pk__in=inventory_ids)
    }

    recommendation_badges_by_inventory_id = {
        product.preferred_inventory_id: getattr(
            product,
            "reorder_recommendation_badge",
            "",
        )
        for product in selected_products
        if product.preferred_inventory_id
    }

    suggested_inventories: list[Inventory] = []

    for inventory_id in inventory_ids:
        inventory = inventories_by_id.get(inventory_id)

        if inventory is None:
            continue

        inventory.reorder_recommendation_badge = (
            recommendation_badges_by_inventory_id.get(inventory_id, "")
        )
        suggested_inventories.append(inventory)

    return suggested_inventories