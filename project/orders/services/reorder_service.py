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

from carts.services import (
    CartOwner,
    CartStockLimitExceeded,
    _get_effective_unit_price,
    cart_add_item_for_owner,
)
from orders.models import Order, OrderItem
from orders.selectors import (
    get_order_detail_for_user,
    get_reorder_suggestion_inventories,
)
from orders.services.order_status import get_order_status_context
from django.apps import apps

User = get_user_model()
Inventory = apps.get_model("products", "Inventory")


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


def _all_product_batches_deleted(*, product) -> bool:
    all_batches = product.inventory_batches.all()
    return (
        all_batches.exists()
        and not all_batches.filter(status=Inventory.BatchStatus.ACTIVE).exists()
    )


def _active_order_item_quantity(item) -> int:
    """
    Return the quantity that should still be reorderable.

    Example:
    - ordered quantity: 3
    - cancelled quantity: 1
    - active reorderable quantity: 2
    """
    original_quantity = int(getattr(item, "quantity", 0) or 0)
    cancelled_quantity = int(getattr(item, "cancelled_quantity", 0) or 0)

    return max(original_quantity - cancelled_quantity, 0)


def _is_cancelled_order_item(item) -> bool:
    return (
        item.status == OrderItem.Status.CANCELLED
        or _active_order_item_quantity(item) <= 0
    )


def _structured_validation_error(
    *,
    code: str,
    message: str,
    data: dict | None = None,
) -> ValidationError:
    return ValidationError(
        {
            "code": code,
            "message": message,
            "data": data or {},
        }
    )


def _get_historical_unit_price(item):
    return (
        getattr(item, "final_unit_price", None)
        or getattr(item, "original_unit_price", None)
        or getattr(item, "unit_price", None)
    )


def _format_unit_price(value) -> str:
    if value is None:
        return "unknown price"
    return f"£{value:.2f}"


def _build_price_change_message(
    *,
    product_name,
    original_price,
    current_price,
    original_producer_name,
    current_producer_name,
    producer_changed,
    pricing_source,
):
    message = (
        f"Unit price updated for {product_name}: "
        f"{_format_unit_price(original_price)} → {_format_unit_price(current_price)}."
    )

    if producer_changed:
        message += (
            f" This is because the replacement item is supplied by "
            f"{current_producer_name} instead of {original_producer_name}."
        )
    elif pricing_source == "surplus":
        message += " This is because the current item has surplus pricing."
    elif pricing_source == "wholesale":
        message += " This is because the current quantity uses wholesale pricing."
    else:
        message += " This is because the current unit price is different from the previous order."

    return message


def _reason_payload(
    *,
    code: str,
    fallback_message: str,
    data: dict | None = None,
) -> dict:
    """
    Build a structured item-level reorder reason.

    The backend identifies the rule. The frontend decides the final wording.
    """
    return {
        "reason_code": code,
        "reason": fallback_message,
        "reason_data": data or {},
    }


def _get_preferred_active_inventory_for_product(*, product):
    """
    Earliest sellable active batch for this product.

    This mirrors the product-detail behaviour:
    - batch must be ACTIVE
    - batch must have remaining stock
    - batch must not be expired
    - earliest expiry wins
    """
    today = timezone.localdate()

    return (
        product.inventory_batches.filter(
            status=Inventory.BatchStatus.ACTIVE,
            remaining_quantity__gt=0,
            expiry_date__gte=today,
        )
        .order_by("expiry_date", "created_at")
        .first()
    )


def _get_fallback_active_inventory_for_reason(*, product):
    """
    Earliest ACTIVE batch regardless of stock/expiry.

    Used only to produce a precise unavailable reason when no sellable batch exists.
    """
    return (
        product.inventory_batches.filter(status=Inventory.BatchStatus.ACTIVE)
        .order_by("expiry_date", "created_at")
        .first()
    )


def _inventory_reorderable(inventory):
    """
    Determine whether an inventory batch is still valid for reorder use.
    """
    today = timezone.localdate()
    product = inventory.product

    if inventory.status != Inventory.BatchStatus.ACTIVE:
        if _all_product_batches_deleted(product=product):
            return False, "Product no longer available."
        return False, "This batch is no longer available."

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


def _is_wholesale_customer(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False

    customer = getattr(user, "customer_profile", None)
    if not customer:
        return False

    return customer.organisation_type in {"BUSINESS", "COMMUNITY_GROUP"}


def _build_pricing_context(*, user: User, inventory, requested_quantity: int) -> dict:
    product = inventory.product
    evaluated_quantity = min(requested_quantity, inventory.remaining_quantity)

    base_unit_price = product.price

    surplus_active = inventory.surplus_status == inventory.SurplusStatus.SURPLUS_ACTIVE
    surplus_unit_price = inventory.get_discounted_price() if surplus_active else None

    wholesale_allowed = _is_wholesale_customer(user)

    if wholesale_allowed:
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
    else:
        wholesale_qs = product.product_wholesale.none()
        matched_wholesale_tier = None
        next_wholesale_tier = None
        wholesale_unit_price = None

    effective_unit_price = _get_effective_unit_price(
        inventory_id=inventory.pk,
        qty=evaluated_quantity,
        wholesale_allowed=wholesale_allowed,
    )

    if surplus_active and wholesale_unit_price is not None:
        pricing_source = (
            "surplus" if effective_unit_price == surplus_unit_price else "wholesale"
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
            "discount_percentage": (
                inventory.surplus_discount_percentage if surplus_active else None
            ),
            "discounted_unit_price": surplus_unit_price,
        },
        "wholesale": {
            "has_wholesale_tiers": wholesale_allowed
            and product.product_wholesale.exists(),
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
    user: User,
    product,
    original_producer_id: int,
    requested_quantity: int,
    excluded_product_ids: set[int] | None = None,
) -> list[dict]:
    """
    Build live alternative candidates for one historical order item.

    Each alternative product should expose only its preferred active batch,
    not multiple batches for the same product.
    """
    suggestion_inventories = get_reorder_suggestion_inventories(
        source_product=product,
        original_producer_id=original_producer_id,
        limit=3,
        excluded_product_ids=excluded_product_ids,
    )

    match_basis = _get_match_basis_for_product(product)
    candidates: list[dict] = []
    seen_product_ids: set[int] = set()

    for inventory in suggestion_inventories:
        suggested_product = inventory.product
        recommendation_badge = getattr(
            inventory,
            "reorder_recommendation_badge",
            "",
        )

        if suggested_product.pk in seen_product_ids:
            continue

        preferred_inventory = _get_preferred_active_inventory_for_product(
            product=suggested_product
        )
        if preferred_inventory is None:
            continue

        seen_product_ids.add(suggested_product.pk)

        pricing = _build_pricing_context(
            user=user,
            inventory=preferred_inventory,
            requested_quantity=requested_quantity,
        )

        candidates.append(
            {
                "product": suggested_product,
                "inventory": preferred_inventory,
                "available_quantity": preferred_inventory.remaining_quantity,
                "match_basis": match_basis,
                "recommendation_badge": recommendation_badge,
                "serialized": {
                    "product_id": suggested_product.pk,
                    "product_name": suggested_product.name,
                    "producer_id": suggested_product.producer_id,
                    "producer_name": suggested_product.producer.farm_name,
                    "inventory_id": preferred_inventory.pk,
                    "available_quantity": preferred_inventory.remaining_quantity,
                    "current_price": pricing["effective_unit_price"],
                    "pricing": pricing,
                    "category_id": suggested_product.category_id,
                    "category_name": suggested_product.category.name,
                    "product_type_id": getattr(
                        suggested_product, "product_type_id", None
                    ),
                    "product_type_name": getattr(
                        getattr(suggested_product, "product_type", None),
                        "name",
                        None,
                    ),
                    "match_basis": match_basis,
                    "recommendation_badge": recommendation_badge,
                },
            }
        )

    return candidates


def _serialise_suggested_items_from_candidates(
    suggestion_candidates: list[dict],
) -> list[dict]:
    return [candidate["serialized"] for candidate in suggestion_candidates]


def _build_original_candidate(*, item) -> tuple[dict | None, str | None]:
    """
    Build the current live original-product candidate for one order item.

    Important:
    - do not reuse the historical batch blindly
    - resolve the current preferred active batch for the same product
    """
    product = item.product

    reorderable, reason = _product_reorderable(product)
    if not reorderable:
        return None, reason

    if _all_product_batches_deleted(product=product):
        return None, "Product no longer available."

    current_inventory = _get_preferred_active_inventory_for_product(product=product)
    if current_inventory is not None:
        return (
            {
                "product": product,
                "inventory": current_inventory,
                "available_quantity": current_inventory.remaining_quantity,
                "match_basis": "original",
            },
            None,
        )

    fallback_inventory = _get_fallback_active_inventory_for_reason(product=product)
    if fallback_inventory is None:
        return None, "Product is not currently available."

    inventory_ok, inventory_reason = _inventory_reorderable(fallback_inventory)
    if not inventory_ok:
        return None, inventory_reason

    if fallback_inventory.remaining_quantity <= 0:
        return None, "Product batch is out of stock."

    return None, "Product cannot be reordered."


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
            raise _structured_validation_error(
                code="invalid_reorder_selection_item",
                message="One selected item does not belong to this order.",
                data={
                    "field": "selections",
                    "order_item_id": order_item_id,
                },
            )

        if order_item_id in selection_map:
            raise _structured_validation_error(
                code="duplicate_reorder_selection_item",
                message="A reorder item was selected more than once.",
                data={
                    "field": "selections",
                    "order_item_id": order_item_id,
                },
            )

        selection_map[order_item_id] = selection

    return selection_map


def _normalise_reorder_quantity(
    *,
    selected_quantity,
    default_quantity: int,
) -> tuple[int | None, str | None]:
    """
    Validate and clamp the selected reorder quantity.

    The maximum allowed reorder quantity is the active historical quantity,
    not the original ordered quantity.

    This protects the backend even if the frontend sends the old full quantity
    for a partially cancelled item.
    """
    if selected_quantity is None:
        return default_quantity, None

    try:
        quantity = int(selected_quantity)
    except (TypeError, ValueError):
        return None, "Selected reorder quantity must be a whole number."

    if quantity <= 0:
        return None, "Selected reorder quantity must be at least 1."

    return min(quantity, default_quantity), None


def _resolve_candidate_for_item(
    *,
    item,
    selection: dict | None,
    original_candidate: dict | None,
    suggestion_candidates: list[dict],
    default_quantity: int,
) -> tuple[dict | None, str | None, int | None]:
    if selection is None:
        if original_candidate is None:
            return None, None, None
        return original_candidate, None, default_quantity

    action = selection["action"]

    if action == "skip":
        return None, "skipped", None

    selected_quantity, quantity_error = _normalise_reorder_quantity(
        selected_quantity=selection.get("quantity"),
        default_quantity=default_quantity,
    )

    if quantity_error:
        return None, quantity_error, None

    if action == "keep":
        if original_candidate is None:
            return (
                None,
                "The original product is no longer available for reorder.",
                None,
            )

        selected_product_id = selection.get("selected_product_id")
        selected_inventory_id = selection.get("inventory_id")

        if (
            selected_product_id is not None
            and selected_product_id != original_candidate["product"].pk
        ):
            return (
                None,
                "Selected product does not match the original reorder item.",
                None,
            )

        if (
            selected_inventory_id is not None
            and selected_inventory_id != original_candidate["inventory"].pk
        ):
            return (
                None,
                "Selected inventory does not match the original reorder item.",
                None,
            )

        return original_candidate, None, selected_quantity

    if action == "replace":
        selected_product_id = selection.get("selected_product_id")
        selected_inventory_id = selection.get("inventory_id")

        for candidate in suggestion_candidates:
            if (
                candidate["product"].pk == selected_product_id
                and candidate["inventory"].pk == selected_inventory_id
            ):
                return candidate, None, selected_quantity

        return (
            None,
            "Selected replacement is not a valid suggestion for this order item.",
            None,
        )

    return None, "Unsupported reorder action.", None


def _append_unavailable_item(
    *,
    result: dict,
    item,
    reason: str,
    requested_quantity: int,
    suggested_items: list[dict],
    reason_code: str = "reorder_item_unavailable",
    reason_data: dict | None = None,
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
            "reason_code": reason_code,
            "reason_data": reason_data or {},
            "suggested_items": suggested_items,
        }
    )


def _append_producer_changed_item(
    *, result: dict, item, selected_candidate: dict
) -> None:
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

    status_context = get_order_status_context(order)

    if status_context["status_key"] != "completed":
        raise _structured_validation_error(
            code="order_not_reorderable",
            message="This order cannot be reordered.",
            data={
                "order_id": order.id,
                "order_status": status_context["status_key"],
                "status_display": status_context["status_display"],
            },
        )

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
    order_product_ids = {
        item.product_id for item in order.items.all() if item.product_id
    }

    for item in order.items.all():
        active_quantity = _active_order_item_quantity(item)
        if _is_cancelled_order_item(item):
            skipped_count += 1
            continue

        suggestion_candidates = _build_suggestion_candidates(
            user=user,
            product=item.product,
            original_producer_id=item.producer_id,
            requested_quantity=active_quantity,
            excluded_product_ids=order_product_ids,
        )
        suggested_items = _serialise_suggested_items_from_candidates(
            suggestion_candidates
        )

        original_candidate, original_unavailable_reason = _build_original_candidate(
            item=item
        )
        selection = selection_map.get(item.pk)

        if selection is None and original_candidate is None:
            _append_unavailable_item(
                result=result,
                item=item,
                reason=original_unavailable_reason or "Product cannot be reordered.",
                requested_quantity=active_quantity,
                suggested_items=suggested_items,
            )
            continue

        selected_candidate, rejection_reason, selected_quantity = (
            _resolve_candidate_for_item(
                item=item,
                selection=selection,
                original_candidate=original_candidate,
                suggestion_candidates=suggestion_candidates,
                default_quantity=active_quantity,
            )
        )

        if rejection_reason == "skipped":
            skipped_count += 1
            continue

        if selected_candidate is None:
            _append_unavailable_item(
                result=result,
                item=item,
                reason=rejection_reason
                or original_unavailable_reason
                or "Product cannot be reordered.",
                requested_quantity=selected_quantity or active_quantity,
                suggested_items=suggested_items,
            )
            continue

        selected_product = selected_candidate["product"]
        selected_inventory = selected_candidate["inventory"]
        requested_quantity = selected_quantity or active_quantity
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
                    "reason_code": "reorder_quantity_reduced",
                    "reason_data": {
                        "requested_quantity": requested_quantity,
                        "available_quantity": available_quantity,
                        "added_quantity": quantity_to_add,
                    },
                }
            )

        pricing = _build_pricing_context(
            user=user,
            inventory=selected_inventory,
            requested_quantity=quantity_to_add,
        )
        current_unit_price = pricing["effective_unit_price"]

        historical_unit_price = _get_historical_unit_price(item)

        producer_changed = selected_product.producer_id != item.producer_id
        original_producer_name = item.producer.farm_name
        current_producer_name = selected_product.producer.farm_name

        if (
            historical_unit_price is not None
            and historical_unit_price != current_unit_price
        ):
            result["price_changed_items"].append(
                {
                    "order_item_id": item.pk,
                    "product_id": selected_product.pk,
                    "product_name": selected_product.name,
                    "original_price": historical_unit_price,
                    "current_price": current_unit_price,
                    "pricing_source": pricing["pricing_source"],
                    "surplus_active": pricing["surplus"]["is_active"],
                    "wholesale_active_for_quantity": pricing["wholesale"][
                        "active_for_quantity"
                    ],
                    "producer_changed": producer_changed,
                    "original_producer_id": item.producer_id,
                    "original_producer_name": original_producer_name,
                    "current_producer_id": selected_product.producer_id,
                    "current_producer_name": current_producer_name,
                    "message": _build_price_change_message(
                        product_name=selected_product.name,
                        original_price=historical_unit_price,
                        current_price=current_unit_price,
                        original_producer_name=original_producer_name,
                        current_producer_name=current_producer_name,
                        producer_changed=producer_changed,
                        pricing_source=pricing["pricing_source"],
                    ),
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
                "recommendation_badge": selected_candidate.get(
                    "recommendation_badge",
                    "",
                ),
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
            except CartStockLimitExceeded as exc:
                _append_unavailable_item(
                    result=result,
                    item=item,
                    reason=exc.message,
                    requested_quantity=requested_quantity,
                    suggested_items=suggested_items,
                    reason_code=exc.code,
                    reason_data=exc.detail.get("data", {}),
                )
            except ValidationError as exc:
                _append_unavailable_item(
                    result=result,
                    item=item,
                    reason="This item could not be added to the cart.",
                    requested_quantity=requested_quantity,
                    suggested_items=suggested_items,
                    reason_code="reorder_cart_add_failed",
                    reason_data={
                        "detail": getattr(exc, "detail", str(exc)),
                    },
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
