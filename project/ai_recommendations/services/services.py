import math
from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from orders.models import Order, OrderItem
from products.models import Inventory, Product

from ..models import ProductInteraction


@dataclass(frozen=True)
class SeedEvent:
    """
    Internal representation of a customer-product interaction used for
    recommendation ranking.
    """

    product: Product
    weight: float
    event_type: str


@dataclass(frozen=True)
class RecommendationResult:
    """
    Ranked product recommendation returned to the view/API layer.
    """

    product: Product
    score: float
    reason: str
    signals: dict


def get_live_products_queryset():
    """
    Return products that are safe to recommend.

    Rules:
    - product must be published
    - product must be available
    - at least one active inventory batch must exist
    - active batch must have remaining stock
    - active batch must not be expired
    """
    today = timezone.localdate()

    active_inventory = Inventory.objects.filter(
        product_id=OuterRef("pk"),
        status=Inventory.BatchStatus.ACTIVE,
        remaining_quantity__gt=0,
        expiry_date__gte=today,
    )

    return (
        Product.objects.filter(
            status=Product.Status.PUBLISHED,
            availability_status=Product.Availability_status.AVAILABLE,
        )
        .annotate(has_active_inventory=Exists(active_inventory))
        .filter(has_active_inventory=True)
    )


def get_recommendations_for_request(request, current_product=None, limit=4):
    """
    Build recommendations for the current request.

    Authenticated users are matched through their account.
    Guests are matched through the session key.
    """
    if hasattr(request, "session") and not request.session.session_key:
        request.session.create()

    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key if hasattr(request, "session") else ""

    return get_recommendations(
        user=user,
        session_key=session_key,
        current_product=current_product,
        limit=limit,
    )


def get_recommendations(user=None, session_key="", current_product=None, limit=4):
    """
    Rank live products for Task 1.

    This lightweight integration uses the same conceptual signals as the
    report:
    - behavioural signal: views, add-to-cart events, transactions
    - content signal: product type and category similarity
    - deployment rules: only live, in-stock, unexpired products
    - explainability: reason and signal breakdown returned with each item
    """
    seed_events = _get_seed_events(
        user=user,
        session_key=session_key,
        current_product=current_product,
    )

    candidate_qs = (
        get_live_products_queryset()
        .select_related("producer", "category", "product_type")
        .distinct()
    )

    if current_product is not None:
        candidate_qs = candidate_qs.exclude(pk=current_product.pk)

    candidates = list(candidate_qs.order_by("-created_at")[:250])

    if not candidates:
        return []

    popularity_scores = _get_popularity_scores(
        product_ids=[product.pk for product in candidates]
    )

    ranked_results = [
        _score_candidate(
            candidate=candidate,
            seed_events=seed_events,
            popularity_scores=popularity_scores,
        )
        for candidate in candidates
    ]

    ranked_results.sort(
        key=lambda result: (result.score, result.product.created_at),
        reverse=True,
    )

    return ranked_results[:limit]


def _get_seed_events(user=None, session_key="", current_product=None):
    """
    Collect recent behaviour from:
    - tracked web interactions
    - completed order history
    - current product context
    """
    seed_events = []

    interaction_filters = []

    if user is not None:
        interaction_filters.append(Q(user=user))

    if session_key:
        interaction_filters.append(Q(session_key=session_key))

    if interaction_filters:
        query = interaction_filters[0]

        for extra_filter in interaction_filters[1:]:
            query |= extra_filter

        interactions = (
            ProductInteraction.objects.filter(query)
            .select_related(
                "product",
                "product__producer",
                "product__category",
                "product__product_type",
            )
            .order_by("-created_at")[:30]
        )

        for interaction in interactions:
            seed_events.append(
                SeedEvent(
                    product=interaction.product,
                    weight=interaction.weight,
                    event_type=interaction.event_type,
                )
            )

    if user is not None:
        completed_items = (
            OrderItem.objects.filter(
                order__user=user,
                order__status=Order.Status.COMPLETED,
            )
            .select_related(
                "product",
                "product__producer",
                "product__category",
                "product__product_type",
            )
            .order_by("-order__order_date")[:30]
        )

        for item in completed_items:
            seed_events.append(
                SeedEvent(
                    product=item.product,
                    weight=ProductInteraction.weight_for_event(
                        ProductInteraction.EventType.TRANSACTION
                    ),
                    event_type=ProductInteraction.EventType.TRANSACTION,
                )
            )

    if current_product is not None:
        seed_events.append(
            SeedEvent(
                product=current_product,
                weight=1.0,
                event_type="current_product_context",
            )
        )

    return seed_events


def _get_popularity_scores(product_ids):
    """
    Build a small collaborative/popularity signal from marketplace
    interactions and completed order quantities.
    """
    scores = defaultdict(float)

    interaction_rows = (
        ProductInteraction.objects.filter(product_id__in=product_ids)
        .values("product_id", "event_type")
        .annotate(total=Count("id"))
    )

    for row in interaction_rows:
        scores[row["product_id"]] += (
            row["total"]
            * ProductInteraction.weight_for_event(row["event_type"])
        )

    order_rows = (
        OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED,
            product_id__in=product_ids,
        )
        .values("product_id")
        .annotate(quantity_total=Sum("quantity"))
    )

    transaction_weight = ProductInteraction.weight_for_event(
        ProductInteraction.EventType.TRANSACTION
    )

    for row in order_rows:
        scores[row["product_id"]] += (
            float(row["quantity_total"] or 0) * transaction_weight
        )

    return scores


def _score_candidate(candidate, seed_events, popularity_scores):
    """
    Score a candidate product against recent interaction history.

    The score is intentionally transparent for demonstration. Each signal
    can be shown in the interface as a lightweight explanation.
    """
    signals = {
        "direct_history": 0.0,
        "content_similarity": 0.0,
        "producer_match": 0.0,
        "marketplace_popularity": min(
            math.log1p(popularity_scores.get(candidate.pk, 0.0)),
            8.0,
        ),
    }

    matched_directly = False
    matched_product_type = False
    matched_category = False

    for seed_event in seed_events:
        seed_product = seed_event.product
        weight = seed_event.weight

        if candidate.pk == seed_product.pk:
            signals["direct_history"] += weight * 4.0
            matched_directly = True

        if (
            candidate.product_type_id
            and seed_product.product_type_id
            and candidate.product_type_id == seed_product.product_type_id
        ):
            signals["content_similarity"] += weight * 3.0
            matched_product_type = True

        elif candidate.category_id == seed_product.category_id:
            signals["content_similarity"] += weight * 1.5
            matched_category = True

        if candidate.producer_id == seed_product.producer_id:
            signals["producer_match"] += weight * 0.4

    score = (
        signals["direct_history"]
        + signals["content_similarity"]
        + signals["producer_match"]
        + signals["marketplace_popularity"]
    )

    reason = _build_reason(
        matched_directly=matched_directly,
        matched_product_type=matched_product_type,
        matched_category=matched_category,
        marketplace_popularity=signals["marketplace_popularity"],
    )

    return RecommendationResult(
        product=candidate,
        score=round(score, 3),
        reason=reason,
        signals={key: round(value, 3) for key, value in signals.items()},
    )


def _build_reason(
    matched_directly,
    matched_product_type,
    matched_category,
    marketplace_popularity,
):
    """
    Return a short user-facing explanation for the recommendation.
    """
    if matched_directly:
        return "Previously viewed, added to basket, or ordered."

    if matched_product_type:
        return "Matches the same product type as recent activity."

    if matched_category:
        return "Matches the same category as recent activity."

    if marketplace_popularity > 0:
        return "Popular with customers based on recent marketplace behaviour."

    return "Available product shown while interaction history grows."