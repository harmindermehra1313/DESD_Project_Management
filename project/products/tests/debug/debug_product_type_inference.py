# docker compose exec web python manage.py shell -c "exec(open('products/tests/debug/debug_product_type_inference.py').read())"
"""
Debug product type inference for producer products.

Purpose:
- Create temporary mock categories.
- Create temporary mock products using the same backend inference helper.
- Print the saved category and product type.
- Delete all mock data at the end.

"""

from decimal import Decimal

from accounts.models import Producer
from products.models import Category, Product, ProductType
from products.services.product_type_inference import get_or_create_inferred_product_type


created_category_ids = []
created_product_type_ids = []
created_product_ids = []

# Set to True if database inspection is needed before cleanup.
# When True, the script pauses until Enter is pressed.
PAUSE_BEFORE_CLEANUP = False


def create_debug_category(name, food_group):
    """
    Create a temporary category for this debug run.
    """
    category = Category.objects.create(
        name=name,
        food_groups=food_group,
        vat=Decimal("0.00"),
        description="Temporary debug category for product type inference.",
    )
    created_category_ids.append(category.id)
    return category


def create_debug_product(name, category, producer):
    """
    Create a temporary product with an inferred product type.
    """
    product_type = get_or_create_inferred_product_type(
        name=name,
        category=category,
    )

    created_product_type_ids.append(product_type.id)

    product = Product.objects.create(
        producer=producer,
        category=category,
        product_type=product_type,
        name=name,
        description="Temporary debug product for product type inference.",
        price=Decimal("1.99"),
        unit=Product.Unit.EACH,
        farm_origin=getattr(producer, "farm_name", None) or "Debug Farm",
        organic_certification_status=Product.OrganicStatus.NOT_CERTIFIED,
        availability_status=Product.Availability_status.AVAILABLE,
        status=Product.Status.PENDING,
    )

    created_product_ids.append(product.id)
    return product


def print_product_result(product):
    """
    Print the saved database result for one mock product.
    """
    product = Product.objects.select_related(
        "category",
        "product_type",
    ).get(id=product.id)

    print("-" * 70)
    print(f"Product:      {product.name}")
    print(f"Category:     {product.category.name}")
    print(
        "Product Type: "
        f"{product.product_type.name if product.product_type else 'None'}"
    )


try:
    producer = Producer.objects.first()

    if not producer:
        print("No producer found. Create at least one producer before running this debug file.")
    else:
        fruit_category = create_debug_category(
            name="DEBUG Fruit",
            food_group=Category.FoodGroups.FRUIT,
        )
        vegetable_category = create_debug_category(
            name="DEBUG Vegetables",
            food_group=Category.FoodGroups.VEGETABLES,
        )
        meat_category = create_debug_category(
            name="DEBUG Meat",
            food_group=Category.FoodGroups.MEAT,
        )

        test_products = [
            create_debug_product(
                name="Royal Gala Apples",
                category=fruit_category,
                producer=producer,
            ),
            create_debug_product(
                name="Seasonal Box",
                category=fruit_category,
                producer=producer,
            ),
            create_debug_product(
                name="Red Potatoes",
                category=vegetable_category,
                producer=producer,
            ),
            create_debug_product(
                name="Chicken Thighs",
                category=meat_category,
                producer=producer,
            ),
        ]

        print("\nDEBUG PRODUCT TYPE INFERENCE RESULTS")

        for product in test_products:
            print_product_result(product)

        print("-" * 70)

        if PAUSE_BEFORE_CLEANUP:
            input("Mock data exists in the database. Press Enter to delete it...")

finally:
    deleted_products, _ = Product.objects.filter(id__in=created_product_ids).delete()
    deleted_product_types, _ = ProductType.objects.filter(
        id__in=created_product_type_ids,
    ).delete()
    deleted_categories, _ = Category.objects.filter(id__in=created_category_ids).delete()

    print("\nDEBUG CLEANUP COMPLETE")
    print(f"Deleted products:      {deleted_products}")
    print(f"Deleted product types: {deleted_product_types}")
    print(f"Deleted categories:    {deleted_categories}")