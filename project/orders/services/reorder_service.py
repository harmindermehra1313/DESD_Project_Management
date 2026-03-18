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

from carts.services import CartOwner, cart_add_item_for_owner
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
def reorder_order(*, user: User, order_id: int) -> dict:
    """
    Attempt to rebuild the current cart from a historical completed order.

    Processing flow:
    1. fetch the order and enforce user ownership
    2. reject non-completed orders
    3. iterate through historical order items
    4. validate product and inventory reorder eligibility
    5. reduce quantity if current stock is lower than the original purchase
    6. attempt to add each valid item into the cart
    7. build a structured result payload for API responses

    Result structure:
    - added_items:
        Items successfully added to cart.
    - unavailable_items:
        Items rejected due to product, inventory, stock, or cart validation issues.
    - quantity_adjusted_items:
        Items added with reduced quantity because of limited stock.
    - price_changed_items:
        Items whose current product price differs from the historical order price.
    - message:
        High-level summary of the final outcome.

    Args:
        user: Authenticated user requesting the reorder.
        order_id: Internal primary key of the historical order.

    Returns:
        dict:
            Structured reorder result suitable for API serialisation.

    Raises:
        ValidationError:
            Raised when the order exists but is not eligible for reorder,
            such as when the order has not been completed.
        Order.DoesNotExist:
            Raised when the order does not exist or does not belong to the user.
    """
    order = get_order_detail_for_user(user=user, order_id=order_id)

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("This order cannot be reordered.")

    owner = CartOwner(user_id=user.id)

    result = {
        "added_items": [],
        "unavailable_items": [],
        "quantity_adjusted_items": [],
        "price_changed_items": [],
        "message": "",
    }

    for item in order.items.all():
        product = item.product
        inventory = item.inventory
        requested_quantity = item.quantity

        reorderable, reason = _product_reorderable(product)
        if not reorderable:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "requested_quantity": requested_quantity,
                    "reason": reason,
                }
            )
            continue

        inventory_ok, inventory_reason = _inventory_reorderable(inventory)
        if not inventory_ok:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "requested_quantity": requested_quantity,
                    "reason": inventory_reason,
                }
            )
            continue

        available_quantity = inventory.remaining_quantity

        if available_quantity <= 0:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "requested_quantity": requested_quantity,
                    "reason": "Product batch is out of stock.",
                }
            )
            continue

        quantity_to_add = min(requested_quantity, available_quantity)

        if item.original_unit_price != product.price:
            result["price_changed_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "original_price": item.original_unit_price,
                    "current_price": product.price,
                }
            )

        if quantity_to_add < requested_quantity:
            result["quantity_adjusted_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "requested_quantity": requested_quantity,
                    "added_quantity": quantity_to_add,
                    "reason": "Quantity reduced due to limited stock.",
                }
            )

        try:
            cart_add_item_for_owner(
                owner=owner,
                inventory_id=inventory.pk,
                quantity=quantity_to_add,
            )
        except ValidationError as exc:
            result["unavailable_items"].append(
                {
                    "product_id": product.pk,
                    "product_name": product.name,
                    "producer_id": item.producer_id,
                    "producer_name": str(item.producer),
                    "requested_quantity": requested_quantity,
                    "reason": str(exc),
                }
            )
            continue

        result["added_items"].append(
            {
                "product_id": product.pk,
                "product_name": product.name,
                "producer_id": item.producer_id,
                "producer_name": str(item.producer),
                "requested_quantity": requested_quantity,
                "added_quantity": quantity_to_add,
                "inventory_id": inventory.pk,
            }
        )

    added = len(result["added_items"])
    unavailable = len(result["unavailable_items"])

    if added and unavailable == 0:
        result["message"] = "All items successfully added to cart."
    elif added:
        result["message"] = "Reorder partially completed."
    else:
        result["message"] = "No items could be reordered."

    return result