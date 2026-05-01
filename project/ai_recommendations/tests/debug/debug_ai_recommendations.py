# docker compose exec web python manage.py shell -c "exec(open('ai_recommendations/tests/debug/debug_ai_recommendations.py').read())"
"""
Debug Task 1 AI recommendations.

Purpose:
- Inspect the current lightweight AI recommendation model.
- Print live recommendable products.
- Print stored product interactions.
- Print completed order-history signals.
- Print recommendation outputs for selected users and products.
- Explain why each recommendation was produced.

This file does not create or delete data by default.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from ai_recommendations.models import ProductInteraction
from ai_recommendations.services.services import (
    get_live_products_queryset,
    get_recommendations,
)
from orders.models import Order, OrderItem
from products.models import Product


# ---------------------------------------------------------------------
# DEBUG SETTINGS
# ---------------------------------------------------------------------

# Set to a username/email to debug one user only.
# Leave as None to use the first active user with interactions/orders.
DEBUG_USER_LOGIN = None

# Set to a product ID to debug recommendations from one current product.
# Leave as None to use the first live product.
DEBUG_CURRENT_PRODUCT_ID = None

# Number of recommendations to print.
RECOMMENDATION_LIMIT = 8

# Number of recent interactions/order items to print.
RECENT_EVENT_LIMIT = 20

# Number of live products to print.
LIVE_PRODUCT_LIMIT = 30

# Print recommendations for more than one live product.
PRINT_MULTIPLE_PRODUCT_CONTEXTS = True

# Number of product contexts to test when PRINT_MULTIPLE_PRODUCT_CONTEXTS is True.
PRODUCT_CONTEXT_LIMIT = 5


# ---------------------------------------------------------------------
# SMALL FORMAT HELPERS
# ---------------------------------------------------------------------

def print_header(title):
    """
    Print a large section heading.
    """
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def print_subheader(title):
    """
    Print a smaller section heading.
    """
    print("\n" + "-" * 90)
    print(title)
    print("-" * 90)


def display_user(user):
    """
    Return a readable user label.
    """
    if not user:
        return "Guest / None"

    username = getattr(user, "username", "") or ""
    email = getattr(user, "email", "") or ""

    if username and email:
        return f"{username} <{email}>"

    return username or email or f"User #{user.pk}"


def display_producer(product):
    """
    Return a readable producer label.
    """
    producer = getattr(product, "producer", None)

    if not producer:
        return "Unknown producer"

    return (
        getattr(producer, "farm_name", None)
        or getattr(producer, "business_name", None)
        or getattr(producer, "name", None)
        or str(producer)
    )


def display_product(product):
    """
    Return a readable product label.
    """
    if not product:
        return "None"

    category = product.category.name if product.category_id else "No category"
    product_type = (
        product.product_type.name
        if product.product_type_id
        else "No product type"
    )

    return (
        f"#{product.pk} | {product.name} | "
        f"{category} / {product_type} | "
        f"{display_producer(product)}"
    )


def get_debug_user():
    """
    Return the user selected for debugging.

    Priority:
    1. DEBUG_USER_LOGIN if provided.
    2. First active user with stored recommendation interactions.
    3. First active user with completed orders.
    4. First active user.
    """
    User = get_user_model()

    if DEBUG_USER_LOGIN:
        username_field = User.USERNAME_FIELD

        user = (
            User._default_manager.filter(
                **{username_field: DEBUG_USER_LOGIN}
            ).first()
            or User._default_manager.filter(email=DEBUG_USER_LOGIN).first()
            or User._default_manager.filter(username=DEBUG_USER_LOGIN).first()
        )

        return user

    interaction_user_id = (
        ProductInteraction.objects.filter(user__isnull=False)
        .values_list("user_id", flat=True)
        .first()
    )

    if interaction_user_id:
        return User._default_manager.filter(pk=interaction_user_id).first()

    order_user_id = (
        Order.objects.filter(
            user__isnull=False,
            status=Order.Status.COMPLETED,
        )
        .values_list("user_id", flat=True)
        .first()
    )

    if order_user_id:
        return User._default_manager.filter(pk=order_user_id).first()

    return User._default_manager.filter(is_active=True).first()


def get_debug_current_product():
    """
    Return the current product context used for the recommender.
    """
    live_products = get_live_products_queryset().select_related(
        "producer",
        "category",
        "product_type",
    )

    if DEBUG_CURRENT_PRODUCT_ID:
        return live_products.filter(pk=DEBUG_CURRENT_PRODUCT_ID).first()

    return live_products.order_by("-created_at").first()


# ---------------------------------------------------------------------
# DEBUG OUTPUT FUNCTIONS
# ---------------------------------------------------------------------

def print_model_configuration():
    """
    Print the simple event weighting used by the demo model.
    """
    print_header("TASK 1 AI RECOMMENDER DEBUG")

    print(f"Run time: {timezone.now()}")
    print("\nEvent weights:")

    for event_type, label in ProductInteraction.EventType.choices:
        print(
            f"  {label:<12} "
            f"event_type={event_type:<12} "
            f"weight={ProductInteraction.weight_for_event(event_type)}"
        )


def print_database_summary():
    """
    Print high-level data availability.
    """
    print_subheader("DATABASE SUMMARY")

    live_count = get_live_products_queryset().count()
    product_count = Product.objects.count()
    interaction_count = ProductInteraction.objects.count()
    completed_order_count = Order.objects.filter(
        status=Order.Status.COMPLETED,
    ).count()
    completed_item_count = OrderItem.objects.filter(
        order__status=Order.Status.COMPLETED,
    ).count()

    print(f"All products:                  {product_count}")
    print(f"Live recommendable products:   {live_count}")
    print(f"Stored AI interactions:        {interaction_count}")
    print(f"Completed orders:              {completed_order_count}")
    print(f"Completed order items:         {completed_item_count}")


def print_live_products():
    """
    Print products that pass the recommender's live-product filter.
    """
    print_subheader("LIVE RECOMMENDABLE PRODUCTS")

    products = list(
        get_live_products_queryset()
        .select_related("producer", "category", "product_type")
        .order_by("-created_at")[:LIVE_PRODUCT_LIMIT]
    )

    if not products:
        print("No live recommendable products found.")
        print(
            "Check product status, availability status, active inventory, "
            "remaining quantity and expiry date."
        )
        return

    for index, product in enumerate(products, start=1):
        print(f"{index:02}. {display_product(product)}")


def print_interaction_summary():
    """
    Print stored recommendation interactions grouped by event type.
    """
    print_subheader("STORED PRODUCT INTERACTIONS")

    rows = (
        ProductInteraction.objects.values("event_type", "source")
        .annotate(total=Count("id"))
        .order_by("event_type", "source")
    )

    if not rows:
        print("No ProductInteraction rows found yet.")
        print("Open product pages or seed demo data to create interaction rows.")
        return

    for row in rows:
        weight = ProductInteraction.weight_for_event(row["event_type"])
        weighted_total = row["total"] * weight

        print(
            f"event={row['event_type']:<12} "
            f"source={row['source']:<14} "
            f"count={row['total']:<5} "
            f"weight={weight:<4} "
            f"weighted_total={weighted_total}"
        )


def print_recent_user_interactions(user):
    """
    Print recent tracked interactions for the selected debug user.
    """
    print_subheader("RECENT DEBUG USER INTERACTIONS")

    if not user:
        print("No user selected.")
        return

    print(f"Debug user: {display_user(user)}")

    interactions = (
        ProductInteraction.objects.filter(user=user)
        .select_related(
            "product",
            "product__producer",
            "product__category",
            "product__product_type",
        )
        .order_by("-created_at")[:RECENT_EVENT_LIMIT]
    )

    if not interactions:
        print("No stored ProductInteraction rows for this user.")
        return

    for interaction in interactions:
        print(
            f"{interaction.created_at} | "
            f"{interaction.event_type:<12} | "
            f"weight={interaction.weight:<4} | "
            f"{display_product(interaction.product)}"
        )


def print_completed_order_signals(user):
    """
    Print completed order items used as strong transaction signals.
    """
    print_subheader("COMPLETED ORDER-HISTORY SIGNALS")

    if not user:
        print("No user selected.")
        return

    items = (
        OrderItem.objects.filter(
            order__user=user,
            order__status=Order.Status.COMPLETED,
        )
        .select_related(
            "order",
            "product",
            "product__producer",
            "product__category",
            "product__product_type",
        )
        .order_by("-order__order_date")[:RECENT_EVENT_LIMIT]
    )

    if not items:
        print("No completed order items found for this user.")
        return

    transaction_weight = ProductInteraction.weight_for_event(
        ProductInteraction.EventType.TRANSACTION,
    )

    for item in items:
        print(
            f"{item.order.order_date} | "
            f"order=#{item.order_id:<5} | "
            f"qty={item.quantity:<4} | "
            f"event_weight={transaction_weight:<4} | "
            f"{display_product(item.product)}"
        )


def print_marketplace_popularity():
    """
    Print the raw popularity/collaborative signal before recommendation ranking.
    """
    print_subheader("MARKETPLACE POPULARITY SIGNALS")

    live_product_ids = list(
        get_live_products_queryset().values_list("id", flat=True)
    )

    if not live_product_ids:
        print("No live products available for popularity scoring.")
        return

    interaction_rows = (
        ProductInteraction.objects.filter(product_id__in=live_product_ids)
        .values("product_id", "product__name", "event_type")
        .annotate(total=Count("id"))
        .order_by("product__name", "event_type")
    )

    order_rows = (
        OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED,
            product_id__in=live_product_ids,
        )
        .values("product_id", "product__name")
        .annotate(quantity_total=Sum("quantity"))
        .order_by("product__name")
    )

    if not interaction_rows and not order_rows:
        print("No popularity signals found yet.")
        return

    print("Tracked interaction popularity:")

    if interaction_rows:
        for row in interaction_rows:
            weight = ProductInteraction.weight_for_event(row["event_type"])
            print(
                f"  product=#{row['product_id']:<5} "
                f"{row['product__name']:<35} "
                f"event={row['event_type']:<12} "
                f"count={row['total']:<5} "
                f"weighted={row['total'] * weight}"
            )
    else:
        print("  None")

    print("\nCompleted order popularity:")

    if order_rows:
        transaction_weight = ProductInteraction.weight_for_event(
            ProductInteraction.EventType.TRANSACTION,
        )

        for row in order_rows:
            quantity_total = row["quantity_total"] or 0
            print(
                f"  product=#{row['product_id']:<5} "
                f"{row['product__name']:<35} "
                f"quantity={quantity_total:<5} "
                f"weighted={float(quantity_total) * transaction_weight}"
            )
    else:
        print("  None")


def print_recommendations_for_context(user, current_product):
    """
    Print final recommendation results for one product context.
    """
    print_subheader("FINAL AI RECOMMENDATION RESULTS")

    print(f"Debug user:      {display_user(user)}")
    print(f"Current product: {display_product(current_product)}")

    if not current_product:
        print("No current product context found.")
        return

    results = get_recommendations(
        user=user,
        session_key="",
        current_product=current_product,
        limit=RECOMMENDATION_LIMIT,
    )

    if not results:
        print("No recommendations returned.")
        return

    for index, result in enumerate(results, start=1):
        print("\n" + f"Recommendation #{index}")
        print(f"Product: {display_product(result.product)}")
        print(f"Score:   {result.score}")
        print(f"Reason:  {result.reason}")
        print("Signals:")

        for signal_name, signal_value in result.signals.items():
            print(f"  - {signal_name}: {signal_value}")


def print_multiple_context_results(user):
    """
    Print model output for several product detail page contexts.
    """
    if not PRINT_MULTIPLE_PRODUCT_CONTEXTS:
        return

    print_subheader("MULTIPLE PRODUCT PAGE CONTEXT RESULTS")

    products = list(
        get_live_products_queryset()
        .select_related("producer", "category", "product_type")
        .order_by("-created_at")[:PRODUCT_CONTEXT_LIMIT]
    )

    if not products:
        print("No live products available for multi-context debugging.")
        return

    for current_product in products:
        print_recommendations_for_context(user, current_product)


# ---------------------------------------------------------------------
# MAIN RUNNER
# ---------------------------------------------------------------------

user = get_debug_user()
current_product = get_debug_current_product()

print_model_configuration()
print_database_summary()
print_live_products()
print_interaction_summary()
print_recent_user_interactions(user)
print_completed_order_signals(user)
print_marketplace_popularity()
print_recommendations_for_context(user, current_product)
print_multiple_context_results(user)

print("\nDEBUG COMPLETE")