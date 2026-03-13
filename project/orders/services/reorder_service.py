"""
orders/services/reorder_service.py

Rebuild a user's cart from a previous order.

Business responsibilities:
- validate order ownership
- read historical order items
- verify product is still reorderable
- verify inventory batch is still reorderable
- verify stock availability
- add items to cart through carts.services
- collect reorder result information
"""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from carts.services import CartOwner, cart_add_item_for_owner
from orders.selectors import get_order_detail_for_user
from orders.models import Order

User = get_user_model()



def _product_reorderable(product):
    """
    Determine whether a product can still be reordered.
    """
    if product.status != product.Status.PUBLISHED:
        return False, "Product is no longer published."

    if product.availability_status != product.Availability_status.AVAILABLE:
        return False, "Product is not currently available."

    return True, None


def _inventory_reorderable(inventory):
    """
    Determine whether an inventory batch can still be reordered.
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
    Rebuild cart from a historical completed order.

    Returns structured result describing reorder outcome.
    """
    order = get_order_detail_for_user(user=user, order_id=order_id)

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("Only completed orders can be reordered.")

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
