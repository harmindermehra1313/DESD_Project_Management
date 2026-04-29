# docker compose exec -e DEBUG_USER_ID=27 -e DEBUG_PRODUCT_ID=1 web python manage.py shell -c "exec(open('products/tests/debug/debug_user_product_roles.py').read())"

"""
Debug one user and one product without assuming any allowed roles.

Purpose:
- input a user ID and product ID
- print the actual user model fields
- print the actual related customer/profile model fields
- print the product wholesale, inventory, availability, and badge inputs
- show the raw values needed to decide why a wholesale badge is not visible
"""

import os
from pprint import pprint

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.utils import timezone

from products.models import Inventory, Product, WholesalePrice


ROLE_FIELD_NAMES = [
    "role",
    "account_type",
    "customer_type",
    "user_type",
    "type",
    "customer_category",
    "customer_group",
    "organisation_type",
    "business_type",
]


PROFILE_RELATION_NAMES = [
    "customer_profile",
    "business_profile",
    "community_profile",
    "community_group_profile",
    "producer_profile",
    "profile",
]


def get_required_env_int(name):
    raw_value = os.environ.get(name)

    if not raw_value:
        raise ValueError(f"{name} is required. Example: -e {name}=1")

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number. Current value: {raw_value!r}") from exc


def safe_getattr(obj, field_name, default=None):
    try:
        return getattr(obj, field_name, default)
    except Exception:
        return default


def print_section(title):
    print(f"\n{title}")
    print("-" * 120)


def model_to_simple_dict(obj):
    """
    Print database field values from a Django model instance.
    """
    if not obj:
        return {}

    data = {}

    for field in obj._meta.fields:
        value = getattr(obj, field.name, None)

        if field.is_relation and value is not None:
            data[field.name] = {
                "id": getattr(value, "pk", None),
                "value": str(value),
            }
        else:
            data[field.name] = value

    return data


def print_possible_role_fields(label, obj):
    """
    Print common role/account-type fields if they exist on the object.
    """
    print(f"\n{label} possible role/account fields:")

    found_any = False

    for field_name in ROLE_FIELD_NAMES:
        if hasattr(obj, field_name):
            found_any = True
            print(f"{field_name}: {safe_getattr(obj, field_name)}")

    if not found_any:
        print("No common role/account-type fields found.")


def get_user(user_id):
    User = get_user_model()
    return User.objects.filter(pk=user_id).first()


def get_product(product_id):
    return (
        Product.objects
        .select_related("producer", "category", "product_type")
        .prefetch_related(
            Prefetch(
                "inventory_batches",
                queryset=Inventory.objects.filter(
                    status=Inventory.BatchStatus.ACTIVE,
                ).order_by("expiry_date", "created_at", "pk"),
                to_attr="active_inventory_batches",
            ),
            Prefetch(
                "product_wholesale",
                queryset=WholesalePrice.objects.order_by("min_quantity", "pk"),
                to_attr="wholesale_tiers",
            ),
        )
        .filter(pk=product_id)
        .first()
    )


def get_existing_profiles(user):
    profiles = {}

    for relation_name in PROFILE_RELATION_NAMES:
        profile = safe_getattr(user, relation_name, None)

        if profile:
            profiles[relation_name] = profile

    return profiles


def print_user_output(user):
    print_section("USER MODEL OUTPUT")

    print("User object:", user)
    print("User ID:", user.pk)
    print("User model:", user.__class__.__name__)
    print("Is active:", safe_getattr(user, "is_active", None))
    print("Is staff:", safe_getattr(user, "is_staff", None))
    print("Is superuser:", safe_getattr(user, "is_superuser", None))
    print("Email:", safe_getattr(user, "email", None))
    print("Username:", safe_getattr(user, "username", None))

    print_possible_role_fields("User", user)

    print("\nFull user database fields:")
    pprint(model_to_simple_dict(user), width=120)


def print_profile_outputs(user):
    print_section("RELATED CUSTOMER / PROFILE MODEL OUTPUTS")

    profiles = get_existing_profiles(user)

    if not profiles:
        print("No common related customer/profile model found.")
        print("Checked relations:")
        pprint(PROFILE_RELATION_NAMES, width=120)
        return

    for relation_name, profile in profiles.items():
        print(f"\nRelation name: {relation_name}")
        print("Profile object:", profile)
        print("Profile ID:", profile.pk)
        print("Profile model:", profile.__class__.__name__)

        print_possible_role_fields(f"Profile {relation_name}", profile)

        print("\nFull profile database fields:")
        pprint(model_to_simple_dict(profile), width=120)


def print_product_output(product):
    today = timezone.localdate()

    active_batches = list(getattr(product, "active_inventory_batches", []))

    live_batches = [
        batch
        for batch in active_batches
        if batch.remaining_quantity > 0
        and batch.expiry_date >= today
    ]

    total_live_stock = sum(batch.remaining_quantity for batch in live_batches)
    earliest_live_batch = live_batches[0] if live_batches else None

    wholesale_tiers = list(getattr(product, "wholesale_tiers", []))

    active_wholesale_tier_by_stock = next(
        (
            tier
            for tier in wholesale_tiers
            if total_live_stock >= tier.min_quantity
        ),
        None,
    )

    first_wholesale_tier = wholesale_tiers[0] if wholesale_tiers else None

    surplus_batch = next(
        (
            batch
            for batch in live_batches
            if batch.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE
            and batch.surplus_discount_percentage
            and batch.surplus_discount_percentage > 0
        ),
        None,
    )

    is_disabled = (
        product.availability_status != Product.Availability_status.AVAILABLE
        or total_live_stock <= 0
        or earliest_live_batch is None
    )

    if product.availability_status == Product.Availability_status.DISCONTINUED:
        disabled_reason = "Discontinued"
    elif product.availability_status == Product.Availability_status.OUT_OF_STOCK:
        disabled_reason = "Out of stock"
    elif active_batches and not live_batches:
        disabled_reason = "Expired or out of stock"
    elif is_disabled:
        disabled_reason = "Unavailable"
    else:
        disabled_reason = ""

    low_stock = (
        not is_disabled
        and product.low_stock_threshold is not None
        and product.low_stock_threshold > 0
        and total_live_stock <= product.low_stock_threshold
    )

    print_section("PRODUCT MODEL OUTPUT")

    print("Product object:", product)
    print("Product ID:", product.pk)
    print("Product model:", product.__class__.__name__)
    print("Name:", product.name)
    print("Status:", product.status)
    print("Published value:", Product.Status.PUBLISHED)
    print("Availability status:", product.availability_status)
    print("Available value:", Product.Availability_status.AVAILABLE)
    print("Out of stock value:", Product.Availability_status.OUT_OF_STOCK)
    print("Discontinued value:", Product.Availability_status.DISCONTINUED)
    print("Category:", safe_getattr(product.category, "name", None))
    print("Product type:", safe_getattr(product.product_type, "name", None))
    print("Producer:", safe_getattr(product.producer, "farm_name", None))
    print("Base price:", product.price)
    print("Low stock threshold:", product.low_stock_threshold)

    print("\nFull product database fields:")
    pprint(model_to_simple_dict(product), width=120)

    print_section("INVENTORY OUTPUT")

    print("Today:", today)
    print("Active batch count:", len(active_batches))
    print("Live batch count:", len(live_batches))
    print("Total live stock:", total_live_stock)
    print("Earliest live batch ID:", safe_getattr(earliest_live_batch, "pk", None))

    if not active_batches:
        print("No active inventory batches found.")

    for batch in active_batches:
        print()
        print("Batch ID:", batch.pk)
        print("Remaining quantity:", batch.remaining_quantity)
        print("Expiry date:", batch.expiry_date)
        print("Expired:", batch.expiry_date < today)
        print("Batch status:", batch.status)
        print("Surplus status:", batch.surplus_status)
        print("Surplus active value:", Inventory.SurplusStatus.SURPLUS_ACTIVE)
        print("Surplus discount percentage:", batch.surplus_discount_percentage)
        print("Is live batch:", batch in live_batches)

    print_section("WHOLESALE OUTPUT")

    print("Wholesale tier count:", len(wholesale_tiers))

    if not wholesale_tiers:
        print("No WholesalePrice rows found for this product.")

    for tier in wholesale_tiers:
        print()
        print("WholesalePrice ID:", tier.pk)
        print("Minimum quantity:", tier.min_quantity)
        print("Unit price:", tier.unit_price)
        print("Total live stock meets minimum quantity:", total_live_stock >= tier.min_quantity)

    print()
    print("First wholesale tier ID:", safe_getattr(first_wholesale_tier, "pk", None))
    print("Active wholesale tier by current stock ID:", safe_getattr(active_wholesale_tier_by_stock, "pk", None))

    print_section("BADGE INPUT OUTPUT")

    print("Is disabled:", is_disabled)
    print("Disabled reason:", disabled_reason)
    print("Surplus active:", surplus_batch is not None)
    print("Low stock:", low_stock)
    print("Has any wholesale tier:", first_wholesale_tier is not None)
    print("Has wholesale tier that current stock can satisfy:", active_wholesale_tier_by_stock is not None)

    print_section("RAW JSON-LIKE PRODUCT OUTPUT")

    pprint(
        {
            "id": product.pk,
            "name": product.name,
            "status": product.status,
            "availability_status": product.availability_status,
            "stock": total_live_stock,
            "expiry": (
                earliest_live_batch.expiry_date.strftime("%Y-%m-%d")
                if earliest_live_batch
                else ""
            ),
            "is_disabled": is_disabled,
            "disabled_reason": disabled_reason,
            "surplus_active": surplus_batch is not None,
            "low_stock": low_stock,
            "has_wholesale_tier": first_wholesale_tier is not None,
            "has_wholesale_tier_by_stock": active_wholesale_tier_by_stock is not None,
            "first_wholesale_min_quantity": (
                first_wholesale_tier.min_quantity
                if first_wholesale_tier
                else None
            ),
            "first_wholesale_unit_price": (
                str(first_wholesale_tier.unit_price)
                if first_wholesale_tier
                else None
            ),
        },
        width=120,
    )


def main():
    user_id = get_required_env_int("DEBUG_USER_ID")
    product_id = get_required_env_int("DEBUG_PRODUCT_ID")

    user = get_user(user_id)
    product = get_product(product_id)

    print_section("DEBUG INPUT")
    print("DEBUG_USER_ID:", user_id)
    print("DEBUG_PRODUCT_ID:", product_id)

    if not user:
        print(f"No user found for DEBUG_USER_ID={user_id}")
        return

    if not product:
        print(f"No product found for DEBUG_PRODUCT_ID={product_id}")
        return

    print_user_output(user)
    print_profile_outputs(user)
    print_product_output(product)


main()