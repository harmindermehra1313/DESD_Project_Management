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
from orders.selectors import get_order_detail_for_user

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

        # Check whether the product itself is still reorderable.
        # Example failures:
        # - unpublished product
        # - product marked unavailable
        reorderable, reason = _product_reorderable(product)
        if not reorderable:
            result["unavailable_items"].append({
                "product_id": product.pk,
                "product_name": product.name,
                "requested_quantity": requested_quantity,
                "reason": reason,
            })
            continue

        # Check whether the historical inventory batch is still valid.
        # Example failures:
        # - expired batch
        inventory_ok, inventory_reason = _inventory_reorderable(inventory)
        if not inventory_ok:
            result["unavailable_items"].append({
                "product_id": product.pk,
                "product_name": product.name,
                "requested_quantity": requested_quantity,
                "reason": inventory_reason,
            })
            continue

        # Read the live remaining stock from the inventory batch.
        available_quantity = inventory.remaining_quantity

        # If no stock remains at all, the item cannot be reordered.
        if available_quantity <= 0:
            result["unavailable_items"].append({
                "product_id": product.pk,
                "product_name": product.name,
                "requested_quantity": requested_quantity,
                "reason": "Product batch is out of stock.",
            })
            continue

        quantity_to_add = min(requested_quantity, available_quantity)

        current_unit_price = _get_effective_unit_price(
            inventory_id=inventory.pk,
            qty=quantity_to_add,
        )
        
        if item.original_unit_price != current_unit_price:
            result["price_changed_items"].append({
                "product_id": product.pk,
                "product_name": product.name,
                "original_price": item.original_unit_price,
                "current_price": current_unit_price,
            })
        
        result["addable_items"].append({
            "product_id": product.pk,
            "product_name": product.name,
            "producer_id": item.producer_id,
            "producer_name": str(item.producer),
            "requested_quantity": requested_quantity,
            "added_quantity": quantity_to_add,
            "current_price": current_unit_price,
        })

        # Only perform the actual cart mutation in commit mode.
        if commit:
            try:
                cart_add_item_for_owner(
                    owner=owner,
                    inventory_id=inventory.pk,
                    quantity=quantity_to_add,
                )

                # Record successful cart additions separately from preview items.
                result["added_items"].append({
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": str(item.producer),
                    "requested_quantity": requested_quantity,
                    "added_quantity": quantity_to_add,
                    "inventory_id": inventory.pk,
                })

            except ValidationError as exc:
                # Cart-level validation can still fail even after earlier checks.
                # Example:
                # - producer/cart rules
                # - cart state restrictions
                # - quantity/business validation inside cart service
                result["unavailable_items"].append({
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": str(item.producer),
                    "requested_quantity": requested_quantity,
                    "reason": str(exc),
                })

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