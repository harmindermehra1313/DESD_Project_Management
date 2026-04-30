# docker compose exec web python manage.py shell -c "exec(open('orders/tests/debug/debug_popular_products.py').read())"


from datetime import timedelta

from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.utils import timezone

from orders.models import Order
from products.models import Inventory, Product


def print_popular_products(limit=20):
    today = timezone.localdate()
    trending_cutoff = timezone.now() - timedelta(days=30)

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

    completed_order_filter = Q(order_items__order__status=Order.Status.COMPLETED)

    recent_completed_order_filter = Q(
        order_items__order__status=Order.Status.COMPLETED,
        order_items__order__order_date__gte=trending_cutoff,
    )

    popular_products = (
        Product.objects.select_related("producer", "category", "product_type")
        .filter(status=Product.Status.PUBLISHED)
        .exclude(availability_status=Product.Availability_status.DISCONTINUED)
        .annotate(preferred_inventory_id=Subquery(preferred_inventory_subquery))
        .filter(preferred_inventory_id__isnull=False)
        .annotate(
            completed_order_count=Count(
                "order_items",
                filter=completed_order_filter,
            ),
            total_quantity_sold=Sum(
                "order_items__quantity",
                filter=completed_order_filter,
            ),
            recent_completed_order_count=Count(
                "order_items",
                filter=recent_completed_order_filter,
            ),
            recent_quantity_sold=Sum(
                "order_items__quantity",
                filter=recent_completed_order_filter,
            ),
        )
        .filter(completed_order_count__gt=0)
        .order_by(
            "-completed_order_count",
            "-total_quantity_sold",
            "name",
            "pk",
        )[:limit]
    )

    print("\nPOPULAR LIVE PRODUCTS")
    print("-" * 120)

    if not popular_products:
        print("No popular live products found.")
        return

    for product in popular_products:
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
            "| completed orders:",
            product.completed_order_count,
            "| qty sold:",
            product.total_quantity_sold or 0,
            "| recent orders:",
            product.recent_completed_order_count,
            "| recent qty:",
            product.recent_quantity_sold or 0,
        )


def print_top_by_type(type_name, limit=10):
    today = timezone.localdate()
    trending_cutoff = timezone.now() - timedelta(days=30)

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

    recent_completed_order_filter = Q(
        order_items__order__status=Order.Status.COMPLETED,
        order_items__order__order_date__gte=trending_cutoff,
    )

    products = (
        Product.objects.select_related("producer", "category", "product_type")
        .filter(
            status=Product.Status.PUBLISHED,
            product_type__name__iexact=type_name,
        )
        .exclude(availability_status=Product.Availability_status.DISCONTINUED)
        .annotate(preferred_inventory_id=Subquery(preferred_inventory_subquery))
        .filter(preferred_inventory_id__isnull=False)
        .annotate(
            recent_completed_order_count=Count(
                "order_items",
                filter=recent_completed_order_filter,
            ),
            recent_quantity_sold=Sum(
                "order_items__quantity",
                filter=recent_completed_order_filter,
            ),
        )
        .filter(recent_completed_order_count__gte=2)
        .order_by(
            "-recent_completed_order_count",
            "-recent_quantity_sold",
            "name",
            "pk",
        )[:limit]
    )

    print(f"\nTOP {limit} TRENDING PRODUCTS FOR TYPE: {type_name}")
    print("-" * 120)

    if not products:
        print("No trending products found for this product type.")
        return

    for product in products:
        print(
            product.pk,
            "|",
            product.name,
            "| producer:",
            getattr(product.producer, "farm_name", None),
            "| recent orders:",
            product.recent_completed_order_count,
            "| recent qty:",
            product.recent_quantity_sold or 0,
        )


print_popular_products(limit=20)

# Change this to test another product type.
print_top_by_type("Egg", limit=10)