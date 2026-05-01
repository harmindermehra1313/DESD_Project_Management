# docker compose exec web python manage.py shell -c "exec(open('orders/tests/debug/debug_recent_products.py').read())"

from datetime import timedelta

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from products.models import Inventory, Product


NEW_PRODUCT_LOOKBACK_DAYS = 14


def print_recent_products(days=NEW_PRODUCT_LOOKBACK_DAYS, limit=30):
    today = timezone.localdate()
    new_product_cutoff = timezone.now() - timedelta(days=days)

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

    recent_products = (
        Product.objects.select_related("producer", "category", "product_type")
        .filter(
            status=Product.Status.PUBLISHED,
            created_at__gte=new_product_cutoff,
        )
        .exclude(
            availability_status=Product.Availability_status.DISCONTINUED,
        )
        .annotate(
            preferred_inventory_id=Subquery(preferred_inventory_subquery),
        )
        .filter(
            preferred_inventory_id__isnull=False,
        )
        .order_by("-created_at", "name", "pk")[:limit]
    )

    print(f"\nRECENT LIVE PRODUCTS ADDED IN LAST {days} DAYS")
    print("-" * 120)

    if not recent_products:
        print("No recent live products found.")
        return

    for product in recent_products:
        print(
            product.pk,
            "|",
            product.name,
            "| type:",
            getattr(product.product_type, "name", None),
            "| category:",
            getattr(product.category, "name", None),
            "| producer:",
            getattr(product.producer, "farm_name", None),
            "| created:",
            product.created_at,
            "| preferred inventory:",
            product.preferred_inventory_id,
        )


def print_recent_products_by_type(type_name, days=NEW_PRODUCT_LOOKBACK_DAYS, limit=20):
    today = timezone.localdate()
    new_product_cutoff = timezone.now() - timedelta(days=days)

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

    recent_products = (
        Product.objects.select_related("producer", "category", "product_type")
        .filter(
            status=Product.Status.PUBLISHED,
            product_type__name__iexact=type_name,
            created_at__gte=new_product_cutoff,
        )
        .exclude(
            availability_status=Product.Availability_status.DISCONTINUED,
        )
        .annotate(
            preferred_inventory_id=Subquery(preferred_inventory_subquery),
        )
        .filter(
            preferred_inventory_id__isnull=False,
        )
        .order_by("-created_at", "name", "pk")[:limit]
    )

    print(f"\nRECENT LIVE PRODUCTS FOR TYPE: {type_name}")
    print(f"Window: last {days} days")
    print("-" * 120)

    if not recent_products:
        print("No recent live products found for this product type.")
        return

    for product in recent_products:
        print(
            product.pk,
            "|",
            product.name,
            "| category:",
            getattr(product.category, "name", None),
            "| producer:",
            getattr(product.producer, "farm_name", None),
            "| created:",
            product.created_at,
            "| preferred inventory:",
            product.preferred_inventory_id,
        )


def print_new_badge_candidates(type_name=None, days=NEW_PRODUCT_LOOKBACK_DAYS, limit=20):
    """
    Show products that would qualify for the New badge.

    Rule:
    - product must be published
    - product must not be discontinued
    - product must have active, non-expired stock
    - product must be created within the recent-product window
    """
    today = timezone.localdate()
    new_product_cutoff = timezone.now() - timedelta(days=days)

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

    queryset = (
        Product.objects.select_related("producer", "category", "product_type")
        .filter(
            status=Product.Status.PUBLISHED,
            created_at__gte=new_product_cutoff,
        )
        .exclude(
            availability_status=Product.Availability_status.DISCONTINUED,
        )
        .annotate(
            preferred_inventory_id=Subquery(preferred_inventory_subquery),
        )
        .filter(
            preferred_inventory_id__isnull=False,
        )
    )

    if type_name:
        queryset = queryset.filter(product_type__name__iexact=type_name)

    products = queryset.order_by("-created_at", "name", "pk")[:limit]

    title = "NEW BADGE CANDIDATES"
    if type_name:
        title += f" FOR TYPE: {type_name}"

    print(f"\n{title}")
    print(f"Window: last {days} days")
    print("-" * 120)

    if not products:
        print("No New badge candidates found.")
        return

    for product in products:
        print(
            product.pk,
            "|",
            product.name,
            "| type:",
            getattr(product.product_type, "name", None),
            "| category:",
            getattr(product.category, "name", None),
            "| producer:",
            getattr(product.producer, "farm_name", None),
            "| created:",
            product.created_at,
            "| badge:",
            "New",
        )


print_recent_products(days=14, limit=30)

# Change this to test another product type.
print_recent_products_by_type("Egg", days=14, limit=20)

# This matches the New badge rule.
print_new_badge_candidates(type_name="Egg", days=14, limit=20)