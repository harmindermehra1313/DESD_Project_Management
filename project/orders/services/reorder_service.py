"""
orders/services/reorder_service.py

Purpose:
Rebuild a cart from a previously completed order.

This module contains the business logic for the reorder feature. It reads
a historical order, checks whether each product can still be purchased,
and attempts to add valid items back into the current cart.

Responsibilities:
- validate that the order belongs to the requesting user
- ensure only completed orders can be reordered
- verify that the product is still reorderable
- verify that the inventory batch is still valid
- verify that stock is available
- add valid items to the cart through carts.services
- collect a structured outcome describing success, partial success, or failure

Design notes:
- this module performs write operations and therefore belongs in services
- selector logic remains delegated to orders.selectors
- cart mutation remains delegated to carts.services
- transaction.atomic is used so cart updates run inside one database transaction
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from carts.services import CartOwner, cart_add_item_for_owner, _get_effective_unit_price
from orders.models import Order
from orders.selectors import get_order_detail_for_user, get_reorder_suggestion_inventories

User = get_user_model()


def _product_reorderable(product):
    """
    Determine whether a product is eligible for reordering.

    Current rules:
    - the product must still be published
    - the product must still be marked as available

    Args:
        product:
            Product instance linked to the historical order item.

    Returns:
        tuple[bool, str | None]:
            A boolean indicating reorder eligibility and an optional
            human-readable rejection reason.
    """
    if product.status != product.Status.PUBLISHED:
        return False, "Product is no longer published."

    if product.availability_status != product.Availability_status.AVAILABLE:
        return False, "Product is not currently available."

    return True, None


def _inventory_reorderable(inventory):
    """
    Determine whether an inventory batch is still valid for reorder use.

    Current rule:
    - expired inventory cannot be reordered

    Expiry messaging differs slightly depending on the expiry type so that
    the rejection reason remains precise.

    Args:
        inventory:
            Inventory batch linked to the historical order item.

    Returns:
        tuple[bool, str | None]:
            A boolean indicating reorder eligibility and an optional
            human-readable rejection reason.
    """
    today = timezone.localdate()

    if inventory.expiry_date < today:
        if inventory.expiry_type == inventory.ExpiryType.USE_BY:
            return False, "Product batch has expired (use-by date passed)."
        return False, "Product batch has expired."

    return True, None
def _serialize_wholesale_tier(tier):
    if not tier:
        return None

    return {
        "min_quantity": tier.min_quantity,
        "unit_price": tier.unit_price,
    }

def _build_pricing_context(*, inventory, requested_quantity: int) -> dict:
    product = inventory.product
    evaluated_quantity = min(requested_quantity, inventory.remaining_quantity)

    base_unit_price = product.price

    surplus_active = (
        inventory.surplus_status == inventory.SurplusStatus.SURPLUS_ACTIVE
    )
    surplus_unit_price = (
        inventory.get_discounted_price() if surplus_active else None
    )

    wholesale_qs = product.product_wholesale.order_by("min_quantity")
    matched_wholesale_tier = (
        wholesale_qs.filter(min_quantity__lte=evaluated_quantity)
        .order_by("-min_quantity")
        .first()
    )
    next_wholesale_tier = (
        wholesale_qs.filter(min_quantity__gt=evaluated_quantity)
        .order_by("min_quantity")
        .first()
    )

    wholesale_unit_price = (
        matched_wholesale_tier.unit_price if matched_wholesale_tier else None
    )

    effective_unit_price = _get_effective_unit_price(
        inventory_id=inventory.pk,
        qty=evaluated_quantity,
    )

    if surplus_active and wholesale_unit_price is not None:
        pricing_source = (
            "surplus"
            if effective_unit_price == surplus_unit_price
            else "wholesale"
        )
    elif surplus_active:
        pricing_source = "surplus"
    elif wholesale_unit_price is not None:
        pricing_source = "wholesale"
    else:
        pricing_source = "base"

    return {
        "base_unit_price": base_unit_price,
        "effective_unit_price": effective_unit_price,
        "pricing_source": pricing_source,
        "surplus": {
            "is_active": surplus_active,
            "discount_percentage": inventory.surplus_discount_percentage if surplus_active else None,
            "discounted_unit_price": surplus_unit_price,
        },
        "wholesale": {
            "has_wholesale_tiers": product.product_wholesale.exists(),
            "active_for_quantity": matched_wholesale_tier is not None,
            "evaluated_quantity": evaluated_quantity,
            "matched_tier": _serialize_wholesale_tier(matched_wholesale_tier),
            "next_tier": _serialize_wholesale_tier(next_wholesale_tier),
        },
    }


def _build_suggested_items(*, product, original_producer_id: int, requested_quantity: int) -> list[dict]:
    suggestion_inventories = get_reorder_suggestion_inventories(
        source_product=product,
        original_producer_id=original_producer_id,
        limit=3,
    )

    match_basis = "product_type" if getattr(product, "product_type_id", None) else "category"
    suggestions: list[dict] = []

    for inventory in suggestion_inventories:
        suggested_product = inventory.product
        pricing = _build_pricing_context(
            inventory=inventory,
            requested_quantity=requested_quantity,
        )

        suggestions.append(
            {
                "product_id": suggested_product.pk,
                "product_name": suggested_product.name,
                "producer_id": suggested_product.producer_id,
                "producer_name": suggested_product.producer.farm_name,
                "inventory_id": inventory.pk,
                "available_quantity": inventory.remaining_quantity,
                "current_price": pricing["effective_unit_price"],  # keep for compatibility
                "pricing": pricing,
                "category_id": suggested_product.category_id,
                "category_name": suggested_product.category.name,
                "product_type_id": getattr(suggested_product, "product_type_id", None),
                "product_type_name": getattr(getattr(suggested_product, "product_type", None), "name", None),
                "match_basis": match_basis,
            }
        )

    return suggestions

@transaction.atomic
def reorder_order(*, user: User, order_id: int, commit: bool = True) -> dict:
    """
    Preview or execute a reorder for a previously completed order.

    This service rebuilds reorder information from a historical order and,
    if requested, adds the valid items back into the user's current cart.

    Behaviour:
    - fetch the order belonging to the authenticated user
    - reject the request if the order is not completed
    - inspect each historical order item one by one
    - validate whether the product can still be reordered
    - validate whether the original inventory batch is still valid
    - check current stock availability
    - record any price changes
    - record any quantity reductions caused by lower stock
    - always build preview data in ``addable_items``
    - only mutate the cart when ``commit=True``

    Args:
        user:
            The authenticated user requesting the reorder.
        order_id:
            Primary key of the historical order to reorder from.
        commit:
            Controls whether this call is a preview or a real reorder.

            - ``False``:
              Preview mode only. No cart mutation happens.
              Valid items are returned in ``addable_items``.
            - ``True``:
              Confirm mode. Valid items are added to cart and returned
              in ``added_items``.

    Returns:
        dict:
            A structured response describing the reorder outcome.

            Keys:
            - ``addable_items``:
                Items that are eligible to be reordered based on the
                current product/inventory state. Used mainly for preview.
            - ``added_items``:
                Items actually added to cart during commit mode.
            - ``unavailable_items``:
                Items that could not be reordered, with reasons.
            - ``quantity_adjusted_items``:
                Items whose reorder quantity had to be reduced because
                current stock is lower than the original ordered quantity.
            - ``price_changed_items``:
                Items whose current price differs from the original order price.
            - ``producer_changed_items``:
                Reserved for future producer-change handling.
            - ``message``:
                A summary message describing the overall result.

    Raises:
        ValidationError:
            Raised when the order is not eligible for reorder, such as when
            it is not in completed status.
        Order.DoesNotExist:
            Propagated if the order does not belong to the user or does not exist.

    Transaction behaviour:
        The function is wrapped in ``transaction.atomic`` so that cart updates
        are executed safely as one database transaction in commit mode.
    """
    # Fetch the full order detail for this user.
    # This also enforces ownership at the selector level.
    order = get_order_detail_for_user(user=user, order_id=order_id)

    # Only completed orders are allowed to be reordered.
    # Pending, cancelled, or in-progress orders must be rejected.
    if order.status != Order.Status.COMPLETED:
        raise ValidationError("This order cannot be reordered.")

    # Build the cart owner object once so it can be reused
    # for each valid item during commit mode.
    owner = CartOwner(user_id=user.id)

    # Structured response payload used by both preview and commit flows.
    result = {
        "addable_items": [],
        "added_items": [],
        "unavailable_items": [],
        "quantity_adjusted_items": [],
        "price_changed_items": [],
        "producer_changed_items": [],  # reserved for future enhancement
        "message": "",
    }

    # Process each historical order item independently.
    for item in order.items.all():
        product = item.product
        inventory = item.inventory
        requested_quantity = item.quantity
        producer_name = item.producer.farm_name
        # Suggested Items
        suggested_items = _build_suggested_items(
            product=product,
            original_producer_id=item.producer_id,
            requested_quantity=requested_quantity,
        )
        
        # Check whether the product itself is still reorderable.
        # Example failures:
        # - unpublished product
        # - product marked unavailable
        reorderable, reason = _product_reorderable(product)
        if not reorderable:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": producer_name,
                    "requested_quantity": requested_quantity,
                    "reason": reason,
                    "suggested_items": suggested_items,
                }
            )
            continue

        # Check whether the historical inventory batch is still valid.
        # Example failures:
        # - expired batch
        inventory_ok, inventory_reason = _inventory_reorderable(inventory)
        if not inventory_ok:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": producer_name,
                    "requested_quantity": requested_quantity,
                    "reason": inventory_reason,
                    "suggested_items": suggested_items,
                }
            )
            continue

        # Read the live remaining stock from the inventory batch.
        available_quantity = inventory.remaining_quantity

        # If no stock remains at all, the item cannot be reordered.
        if available_quantity <= 0:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": producer_name,
                    "requested_quantity": requested_quantity,
                    "reason": "Product batch is out of stock.",
                    "suggested_items": suggested_items,
                }
            )
            continue

        quantity_to_add = min(requested_quantity, available_quantity)
        if quantity_to_add < requested_quantity:
            result["quantity_adjusted_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "requested_quantity": requested_quantity,
                    "added_quantity": quantity_to_add,
                    "reason": "Available quantity is lower than originally ordered quantity.",
                }
            )
        pricing = _build_pricing_context(
            inventory=inventory,
            requested_quantity=quantity_to_add,
        )
        current_unit_price = pricing["effective_unit_price"]

        if item.original_unit_price != current_unit_price:
            result["price_changed_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "original_price": item.original_unit_price,
                    "current_price": current_unit_price,
                    "pricing_source": pricing["pricing_source"],
                    "surplus_active": pricing["surplus"]["is_active"],
                    "wholesale_active_for_quantity": pricing["wholesale"]["active_for_quantity"],
                }
            )

        result["addable_items"].append(
            {
                "product_id": product.pk,
                "product_name": product.name,
                "producer_id": item.producer_id,
                "producer_name": producer_name,
                "requested_quantity": requested_quantity,
                "added_quantity": quantity_to_add,
                "current_price": current_unit_price,
                "pricing": pricing,
                "suggested_items": suggested_items,
            }
        )

        # Only perform the actual cart mutation in commit mode.
        if commit:
            try:
                cart_add_item_for_owner(
                    owner=owner,
                    inventory_id=inventory.pk,
                    quantity=quantity_to_add,
                )

                # Record successful cart additions separately from preview items.
                result["added_items"].append(
                    {
                        "product_id": product.pk,
                        "product_name": product.name,
                        "producer_id": item.producer_id,
                        "producer_name": producer_name,
                        "requested_quantity": requested_quantity,
                        "added_quantity": quantity_to_add,
                        "inventory_id": inventory.pk,
                    }
                )

            except ValidationError as exc:
                # Cart-level validation can still fail even after earlier checks.
                # Example:
                # - producer/cart rules
                # - cart state restrictions
                # - quantity/business validation inside cart service
                result["unavailable_items"].append(
                    {
                        "product_id": product.pk,
                        "product_name": product.name,
                        "producer_id": item.producer_id,
                        "producer_name": producer_name,
                        "requested_quantity": requested_quantity,
                        "reason": str(exc),
                        "suggested_items": suggested_items,
                    }
                )

    # Build summary counts for final messaging.
    addable = len(result["addable_items"])
    added = len(result["added_items"])
    unavailable = len(result["unavailable_items"])

    # Preview mode:
    # no cart mutation happened, so the message should describe preview outcome.
    if not commit:
        if addable:
            result["message"] = "Preview generated successfully."
        else:
            result["message"] = "No items can be reordered from this order."
        return result

    # Commit mode:
    # describe actual cart insertion outcome.
    if added and unavailable == 0:
        result["message"] = "All items successfully added to cart."
    elif added:
        result["message"] = "Reorder partially completed."
    else:
        result["message"] = "No items could be reordered."

    return result
