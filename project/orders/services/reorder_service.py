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

from carts.services import CartOwner, _get_effective_unit_price, cart_add_item_for_owner
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

    surplus_active = inventory.surplus_status == inventory.SurplusStatus.SURPLUS_ACTIVE
    surplus_unit_price = inventory.get_discounted_price() if surplus_active else None

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

    wholesale_unit_price = matched_wholesale_tier.unit_price if matched_wholesale_tier else None

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


def _get_match_basis_for_product(product) -> str:
    return "product_type" if getattr(product, "product_type_id", None) else "category"


def _build_suggestion_candidates(
    *,
    product,
    original_producer_id: int,
    requested_quantity: int,
) -> list[dict]:
    """
    Build live alternative candidates for one historical order item.

    Each returned entry keeps both:
    - ORM objects needed for commit-time cart mutation
    - a serialised payload suitable for preview UI rendering
    """
    suggestion_inventories = get_reorder_suggestion_inventories(
        source_product=product,
        original_producer_id=original_producer_id,
        limit=3,
    )

    match_basis = _get_match_basis_for_product(product)
    candidates: list[dict] = []

    for inventory in suggestion_inventories:
        suggested_product = inventory.product
        pricing = _build_pricing_context(
            inventory=inventory,
            requested_quantity=requested_quantity,
        )

        candidates.append(
            {
                "product": suggested_product,
                "inventory": inventory,
                "available_quantity": inventory.remaining_quantity,
                "match_basis": match_basis,
                "serialized": {
                    "product_id": suggested_product.pk,
                    "product_name": suggested_product.name,
                    "producer_id": suggested_product.producer_id,
                    "producer_name": suggested_product.producer.farm_name,
                    "inventory_id": inventory.pk,
                    "available_quantity": inventory.remaining_quantity,
                    "current_price": pricing["effective_unit_price"],
                    "pricing": pricing,
                    "category_id": suggested_product.category_id,
                    "category_name": suggested_product.category.name,
                    "product_type_id": getattr(suggested_product, "product_type_id", None),
                    "product_type_name": getattr(
                        getattr(suggested_product, "product_type", None),
                        "name",
                        None,
                    ),
                    "match_basis": match_basis,
                },
            }
        )

    return candidates


def _serialise_suggested_items_from_candidates(suggestion_candidates: list[dict]) -> list[dict]:
    return [candidate["serialized"] for candidate in suggestion_candidates]


def _build_original_candidate(*, item) -> tuple[dict | None, str | None]:
    """
    Build the original-product candidate for one order item if it is still live.

    Returns:
        tuple[candidate | None, reason | None]
    """
    product = item.product
    inventory = item.inventory

    reorderable, reason = _product_reorderable(product)
    if not reorderable:
        return None, reason

    inventory_ok, inventory_reason = _inventory_reorderable(inventory)
    if not inventory_ok:
        return None, inventory_reason

    available_quantity = inventory.remaining_quantity
    if available_quantity <= 0:
        return None, "Product batch is out of stock."

    return (
        {
            "product": product,
            "inventory": inventory,
            "available_quantity": available_quantity,
            "match_basis": "original",
        },
        None,
    )


def _build_selection_map(*, order, selections: list[dict] | None) -> dict[int, dict]:
    """
    Validate selection references and return them keyed by order_item_id.
    """
    if not selections:
        return {}

    valid_item_ids = {item.pk for item in order.items.all()}
    selection_map: dict[int, dict] = {}

    for selection in selections:
        order_item_id = selection["order_item_id"]

        if order_item_id not in valid_item_ids:
            raise ValidationError(
                {
                    "selections": [
                        f"Order item {order_item_id} does not belong to this order."
                    ]
                }
            )

        if order_item_id in selection_map:
            raise ValidationError(
                {
                    "selections": [
                        f"Duplicate selection received for order item {order_item_id}."
                    ]
                }
            )

        selection_map[order_item_id] = selection

    return selection_map


def _resolve_candidate_for_item(
    *,
    item,
    selection: dict | None,
    original_candidate: dict | None,
    suggestion_candidates: list[dict],
) -> tuple[dict | None, str | None, int | None]:
    """
    Resolve which live candidate should be used for one order item.

    Returns:
        tuple[candidate | None, rejection_reason | None, requested_quantity | None]
    """
    if selection is None:
        if original_candidate is None:
            return None, None, None
        return original_candidate, None, item.quantity

    action = selection["action"]

    if action == "skip":
        return None, "skipped", None

    if action == "keep":
        if original_candidate is None:
            return None, "The original product is no longer available for reorder.", None

        selected_product_id = selection.get("selected_product_id")
        selected_inventory_id = selection.get("inventory_id")

        if selected_product_id is not None and selected_product_id != original_candidate["product"].pk:
            return None, "Selected product does not match the original reorder item.", None

        if selected_inventory_id is not None and selected_inventory_id != original_candidate["inventory"].pk:
            return None, "Selected inventory does not match the original reorder item.", None

        return original_candidate, None, selection["quantity"]

    if action == "replace":
        selected_product_id = selection.get("selected_product_id")
        selected_inventory_id = selection.get("inventory_id")

        for candidate in suggestion_candidates:
            if (
                candidate["product"].pk == selected_product_id
                and candidate["inventory"].pk == selected_inventory_id
            ):
                return candidate, None, selection["quantity"]

        return None, "Selected replacement is not a valid suggestion for this order item.", None

    return None, "Unsupported reorder action.", None


def _append_unavailable_item(
    *,
    result: dict,
    item,
    reason: str,
    requested_quantity: int,
    suggested_items: list[dict],
) -> None:
    result["unavailable_items"].append(
        {
            "order_item_id": item.pk,
            "product_id": item.product.pk,
            "product_name": item.product.name,
            "producer_id": item.producer_id,
            "producer_name": item.producer.farm_name,
            "requested_quantity": requested_quantity,
            "reason": reason,
            "suggested_items": suggested_items,
        }
    )


def _append_producer_changed_item(*, result: dict, item, selected_candidate: dict) -> None:
    selected_product = selected_candidate["product"]

    if selected_product.producer_id == item.producer_id:
        return

    result["producer_changed_items"].append(
        {
            "order_item_id": item.pk,
            "product_id": selected_product.pk,
            "product_name": selected_product.name,
            "original_producer_id": item.producer_id,
            "original_producer_name": item.producer.farm_name,
            "current_producer_id": selected_product.producer_id,
            "current_producer_name": selected_product.producer.farm_name,
        }
    )


@transaction.atomic
def reorder_order(
    *,
    user: User,
    order_id: int,
    commit: bool = True,
    selections: list[dict] | None = None,
) -> dict:
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
    - optionally apply user-provided replacement and quantity selections
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
        selections:
            Optional frontend-provided user choices keyed by order item.
            Each entry may keep the original product, choose a suggested
            replacement, or skip the item entirely.

    Returns:
        dict:
            A structured response describing the reorder outcome.
    """
    order = get_order_detail_for_user(user=user, order_id=order_id)

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("This order cannot be reordered.")

    owner = CartOwner(user_id=user.id)
    selection_map = _build_selection_map(order=order, selections=selections)

    result = {
        "addable_items": [],
        "added_items": [],
        "unavailable_items": [],
        "quantity_adjusted_items": [],
        "price_changed_items": [],
        "producer_changed_items": [],
        "message": "",
    }

    skipped_count = 0

    for item in order.items.all():
        suggestion_candidates = _build_suggestion_candidates(
            product=item.product,
            original_producer_id=item.producer_id,
            requested_quantity=item.quantity,
        )
        suggested_items = _serialise_suggested_items_from_candidates(suggestion_candidates)

        original_candidate, original_unavailable_reason = _build_original_candidate(item=item)
        selection = selection_map.get(item.pk)

        if selection is None and original_candidate is None:
            _append_unavailable_item(
                result=result,
                item=item,
                reason=original_unavailable_reason or "Product cannot be reordered.",
                requested_quantity=item.quantity,
                suggested_items=suggested_items,
            )
            continue

        selected_candidate, rejection_reason, selected_quantity = _resolve_candidate_for_item(
            item=item,
            selection=selection,
            original_candidate=original_candidate,
            suggestion_candidates=suggestion_candidates,
        )

        if rejection_reason == "skipped":
            skipped_count += 1
            continue

        if selected_candidate is None:
            _append_unavailable_item(
                result=result,
                item=item,
                reason=rejection_reason or original_unavailable_reason or "Product cannot be reordered.",
                requested_quantity=selected_quantity or item.quantity,
                suggested_items=suggested_items,
            )
            continue

        selected_product = selected_candidate["product"]
        selected_inventory = selected_candidate["inventory"]
        requested_quantity = selected_quantity or item.quantity
        available_quantity = selected_candidate["available_quantity"]
        quantity_to_add = min(requested_quantity, available_quantity)

        if quantity_to_add < requested_quantity:
            result["quantity_adjusted_items"].append(
                {
                    "order_item_id": item.pk,
                    "product_id": selected_product.pk,
                    "product_name": selected_product.name,
                    "requested_quantity": requested_quantity,
                    "added_quantity": quantity_to_add,
                    "reason": "Available quantity is lower than the requested reorder quantity.",
                }
            )

        pricing = _build_pricing_context(
            inventory=selected_inventory,
            requested_quantity=quantity_to_add,
        )
        current_unit_price = pricing["effective_unit_price"]

        if item.original_unit_price != current_unit_price:
            result["price_changed_items"].append(
                {
                    "order_item_id": item.pk,
                    "product_id": selected_product.pk,
                    "product_name": selected_product.name,
                    "original_price": item.original_unit_price,
                    "current_price": current_unit_price,
                    "pricing_source": pricing["pricing_source"],
                    "surplus_active": pricing["surplus"]["is_active"],
                    "wholesale_active_for_quantity": pricing["wholesale"]["active_for_quantity"],
                }
            )

        _append_producer_changed_item(
            result=result,
            item=item,
            selected_candidate=selected_candidate,
        )

        result["addable_items"].append(
            {
                "order_item_id": item.pk,
                "product_id": selected_product.pk,
                "product_name": selected_product.name,
                "producer_id": selected_product.producer_id,
                "producer_name": selected_product.producer.farm_name,
                "requested_quantity": requested_quantity,
                "added_quantity": quantity_to_add,
                "inventory_id": selected_inventory.pk,
                "available_quantity": available_quantity,
                "current_price": current_unit_price,
                "pricing": pricing,
                "match_basis": selected_candidate["match_basis"],
                "suggested_items": suggested_items,
            }
        )

        if commit:
            try:
                cart_add_item_for_owner(
                    owner=owner,
                    inventory_id=selected_inventory.pk,
                    quantity=quantity_to_add,
                )

                result["added_items"].append(
                    {
                        "order_item_id": item.pk,
                        "product_id": selected_product.pk,
                        "product_name": selected_product.name,
                        "producer_id": selected_product.producer_id,
                        "producer_name": selected_product.producer.farm_name,
                        "requested_quantity": requested_quantity,
                        "added_quantity": quantity_to_add,
                        "inventory_id": selected_inventory.pk,
                    }
                )
            except ValidationError as exc:
                _append_unavailable_item(
                    result=result,
                    item=item,
                    reason=str(exc),
                    requested_quantity=requested_quantity,
                    suggested_items=suggested_items,
                )

    addable = len(result["addable_items"])
    added = len(result["added_items"])
    unavailable = len(result["unavailable_items"])

    if not commit:
        if addable:
            result["message"] = "Preview generated successfully."
        elif skipped_count and unavailable == 0:
            result["message"] = "No items selected for reorder preview."
        else:
            result["message"] = "No items can be reordered from this order."
        return result

    if added and unavailable == 0:
        result["message"] = "All selected items successfully added to cart."
    elif added:
        result["message"] = "Reorder partially completed."
    elif skipped_count and unavailable == 0:
        result["message"] = "No items were selected for reorder."
    else:
        result["message"] = "No items could be reordered."

    return result
