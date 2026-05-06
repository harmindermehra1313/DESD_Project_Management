# carts/services.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional, Union

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Cart, CartItem, CartStatus

Product = apps.get_model("products", "Product")
Inventory = apps.get_model("products", "Inventory")
WholesalePrice = apps.get_model("products", "WholesalePrice")
User = apps.get_model("accounts", "User")
Customer = apps.get_model("accounts", "Customer")


class CartError(Exception):
    """Base domain exception for cart operations."""

    pass


class CartNotFound(CartError):
    pass


class CartNotActive(CartError):
    pass


class CartItemNotFound(CartError):
    pass


class CartStockLimitExceeded(CartError):
    """Raised when requested cart quantity exceeds available stock."""

    code = "cart_stock_limit_exceeded"
    message = "Requested quantity exceeds available stock."

    def __init__(
        self,
        *,
        inventory: Inventory,
        available_stock: Decimal,
        quantity_in_cart: Decimal,
        requested_quantity: Decimal,
        requested_total_quantity: Decimal,
        operation: str,
    ):
        self.inventory = inventory
        self.available_stock = available_stock
        self.quantity_in_cart = quantity_in_cart
        self.requested_quantity = requested_quantity
        self.requested_total_quantity = requested_total_quantity
        self.operation = operation

        max_addable_quantity = max(
            available_stock - quantity_in_cart,
            Decimal("0"),
        )

        self.detail = {
            "code": self.code,
            "message": self.message,
            "data": {
                "operation": operation,
                "inventory_id": inventory.id,
                "product_id": inventory.product_id,
                "product_name": inventory.product.name,
                "available_stock": _quantity_for_api(available_stock),
                "quantity_in_cart": _quantity_for_api(quantity_in_cart),
                "requested_quantity": _quantity_for_api(requested_quantity),
                "requested_total_quantity": _quantity_for_api(requested_total_quantity),
                "max_addable_quantity": _quantity_for_api(max_addable_quantity),
                "max_allowed_quantity": _quantity_for_api(available_stock),
            },
        }

        super().__init__(self.message)


@dataclass(frozen=True)
class CartOwner:
    """Identifies exactly one of: authenticated user OR anonymous session."""

    user_id: Optional[int] = None
    session_key: Optional[str] = None


def _now():
    return timezone.now()


def _to_decimal(q: Union[int, str, Decimal]) -> Decimal:
    if isinstance(q, Decimal):
        return q
    return Decimal(str(q))


def _quantity_for_api(value: Decimal) -> int | str:
    """
    Convert Decimal quantities into JSON-friendly values.

    Whole numbers are returned as integers. Decimal quantities are returned
    as strings to avoid floating point precision issues.
    """
    quantity = Decimal(str(value))

    if quantity == quantity.to_integral_value():
        return int(quantity)

    return str(quantity)


def _assert_owner(owner: CartOwner) -> None:
    # Exactly one must be set
    if bool(owner.user_id) == bool(owner.session_key):
        raise ValueError(
            "CartOwner must have exactly one of user_id or session_key set."
        )


def _all_product_batches_deleted(*, product: Product) -> bool:
    all_batches = product.inventory_batches.all()
    return (
        all_batches.exists()
        and not all_batches.filter(status=Inventory.BatchStatus.ACTIVE).exists()
    )


def _get_sellable_inventory(*, inventory_id: int) -> Inventory:
    """
    Returns inventory only if the batch is still sellable.

    Sellable means:
    - inventory exists
    - product is published
    - product availability is AVAILABLE
    - batch status is ACTIVE
    - batch has stock remaining
    - batch is not expired
    """
    inventory = (
        Inventory.objects.select_related("product").filter(pk=inventory_id).first()
    )

    if inventory is None:
        raise ValidationError("Invalid inventory_id.")

    product = inventory.product

    if product.status != Product.Status.PUBLISHED:
        raise ValidationError("This product is not available for purchase.")

    if product.availability_status != Product.Availability_status.AVAILABLE:
        raise ValidationError("This product is not available for purchase.")

    if inventory.status != Inventory.BatchStatus.ACTIVE:
        if _all_product_batches_deleted(product=product):
            raise ValidationError("Product no longer available.")

        raise ValidationError("This batch is no longer available.")

    if inventory.is_expired():
        raise ValidationError("This batch has expired.")

    if inventory.remaining_quantity <= 0:
        raise ValidationError("This batch is out of stock.")

    return inventory


def _get_preferred_active_inventory_for_product(
    *, product: Product
) -> Inventory | None:
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


def _resolve_inventory_for_cart_add(*, inventory_id: int) -> Inventory:
    requested_inventory = (
        Inventory.objects.select_related("product").filter(pk=inventory_id).first()
    )

    if requested_inventory is None:
        raise ValidationError("Invalid inventory_id.")

    product = requested_inventory.product

    preferred_inventory = _get_preferred_active_inventory_for_product(product=product)

    if preferred_inventory is None:
        # fall back to current validation flow so the user gets the correct error
        return _get_sellable_inventory(inventory_id=inventory_id)

    return preferred_inventory


def _get_inventory_data(*, inventory_id: int) -> tuple[Decimal, Decimal]:
    inventory = _get_sellable_inventory(inventory_id=inventory_id)
    price = inventory.product.price
    remaining = inventory.remaining_quantity
    return Decimal(str(price)), Decimal(str(remaining))


def _is_wholesale_customer_by_user_id(user_id: Optional[int]) -> bool:
    if not user_id:
        return False

    customer = (
        Customer.objects.filter(user_id=user_id).only("organisation_type").first()
    )
    if not customer:
        return False

    return customer.organisation_type in {"BUSINESS", "COMMUNITY_GROUP"}


def _cart_allows_wholesale(cart: Cart) -> bool:
    return _is_wholesale_customer_by_user_id(cart.user_id)


def _get_effective_unit_price(
    *,
    inventory_id: int,
    qty: Decimal,
    wholesale_allowed: bool = False,
) -> Decimal:
    """
    Final pricing logic:
    1. Start from base price
    2. Apply surplus or expiry discount if active
    3. Apply wholesale tier only if eligible
    """

    inventory = _get_sellable_inventory(inventory_id=inventory_id)
    product = inventory.product

    base_price = Decimal(str(product.price))

    # Surplus / Expires Soon discount (batch-level)
    discount_pct = inventory.current_discount_percentage
    if discount_pct > 0:
        discount_factor = (Decimal("100") - discount_pct) / Decimal("100")
        base_price = base_price * discount_factor

    if not wholesale_allowed:
        return base_price

    qty_int = int(qty)

    tier_price = (
        WholesalePrice.objects.filter(
            product_id=product.id,
            min_quantity__lte=qty_int,
        )
        .order_by("-min_quantity")
        .values_list("unit_price", flat=True)
        .first()
    )

    if tier_price is not None:
        tier_price = Decimal(str(tier_price))
        return min(base_price, tier_price)

    return base_price


def cart_new_session_key() -> str:
    # Session-like token; store as string
    return uuid.uuid4().hex


def cart_touch(cart: Cart, *, at=None) -> None:
    at = at or _now()
    Cart.objects.filter(pk=cart.pk).update(last_seen_at=at, updated_at=at)


def validate_stock(
    *,
    inventory_id: int,
    requested_total_quantity: Decimal,
    requested_quantity: Decimal,
    quantity_in_cart: Decimal = Decimal("0"),
    operation: str = "set_quantity",
) -> None:
    inventory = _get_sellable_inventory(inventory_id=inventory_id)
    remaining = Decimal(str(inventory.remaining_quantity or 0))

    if remaining <= 0:
        raise ValidationError("This batch is out of stock.")

    if requested_total_quantity > remaining:
        raise CartStockLimitExceeded(
            inventory=inventory,
            available_stock=remaining,
            quantity_in_cart=quantity_in_cart,
            requested_quantity=requested_quantity,
            requested_total_quantity=requested_total_quantity,
            operation=operation,
        )


@transaction.atomic
def cart_get_or_create_active(*, owner: CartOwner, guest_ttl_days: int = 14) -> Cart:
    _assert_owner(owner)
    now = _now()

    # Authenticated user cart
    if owner.user_id:
        cart = (
            Cart.objects.select_for_update()
            .filter(user_id=owner.user_id, status=CartStatus.ACTIVE)
            .first()
        )
        if cart:
            cart_touch(cart, at=now)
            return cart

        # Create (race-safe)
        try:
            return Cart.objects.create(
                user_id=owner.user_id,
                session_key=None,
                status=CartStatus.ACTIVE,
                last_seen_at=now,
            )
        except IntegrityError:
            cart = Cart.objects.select_for_update().get(
                user_id=owner.user_id, status=CartStatus.ACTIVE
            )
            cart_touch(cart, at=now)
            return cart

    # Guest cart (session_key)

    token = owner.session_key
    if not token:
        raise ValueError("session_key must be set for guest carts.")

    cart = (
        Cart.objects.select_for_update()
        .filter(session_key=token, status=CartStatus.ACTIVE)  # IMPORTANT
        .first()
    )

    # No ACTIVE guest cart -> create one
    if not cart:
        return Cart.objects.create(
            user=None,
            session_key=token,
            status=CartStatus.ACTIVE,
            last_seen_at=now,
            expires_at=now + timedelta(days=guest_ttl_days),
        )

    # ACTIVE but expired -> abandon + create new ACTIVE cart
    if cart.expires_at and cart.expires_at <= now:
        Cart.objects.filter(pk=cart.pk).update(
            status=CartStatus.ABANDONED,
            updated_at=now,
        )
        return Cart.objects.create(
            user=None,
            session_key=token,
            status=CartStatus.ACTIVE,
            last_seen_at=now,
            expires_at=now + timedelta(days=guest_ttl_days),
        )

    cart_touch(cart, at=now)
    return cart


@transaction.atomic
def cart_add_item(
    *, cart: Cart, inventory_id: int, quantity: Union[int, str, Decimal]
) -> CartItem:
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")

    add_qty = _to_decimal(quantity)
    if add_qty <= 0:
        raise ValueError("quantity must be > 0")

    preferred_inventory = _resolve_inventory_for_cart_add(inventory_id=inventory_id)
    inventory_id = preferred_inventory.id

    Cart.objects.select_for_update().filter(pk=cart.pk).get()

    item = (
        CartItem.objects.select_for_update()
        .filter(cart_id=cart.pk, inventory_id=inventory_id)
        .first()
    )

    existing_qty = item.quantity if item else Decimal("0")
    new_qty = existing_qty + add_qty

    validate_stock(
        inventory_id=inventory_id,
        requested_total_quantity=new_qty,
        requested_quantity=add_qty,
        quantity_in_cart=existing_qty,
        operation="add",
    )

    wholesale_allowed = _cart_allows_wholesale(cart)
    unit_price = _get_effective_unit_price(
        inventory_id=inventory_id,
        qty=new_qty,
        wholesale_allowed=wholesale_allowed,
    )

    if item:
        CartItem.objects.filter(pk=item.pk).update(
            quantity=new_qty,
            unit_price=unit_price,
            updated_at=_now(),
        )
        item.quantity = new_qty
        item.unit_price = unit_price
        return item

    try:
        return CartItem.objects.create(
            cart_id=cart.pk,
            inventory_id=inventory_id,
            quantity=new_qty,
            unit_price=unit_price,
        )
    except IntegrityError:
        item = CartItem.objects.select_for_update().get(
            cart_id=cart.pk,
            inventory_id=inventory_id,
        )
        new_qty = (item.quantity or Decimal("0")) + add_qty

        validate_stock(
            inventory_id=inventory_id,
            requested_total_quantity=new_qty,
            requested_quantity=add_qty,
            quantity_in_cart=item.quantity or Decimal("0"),
            operation="add",
        )

        wholesale_allowed = _cart_allows_wholesale(cart)
        unit_price = _get_effective_unit_price(
            inventory_id=inventory_id,
            qty=new_qty,
            wholesale_allowed=wholesale_allowed,
        )

        CartItem.objects.filter(pk=item.pk).update(
            quantity=new_qty,
            unit_price=unit_price,
            updated_at=_now(),
        )
        item.quantity = new_qty
        item.unit_price = unit_price
        return item


@transaction.atomic
def cart_set_item_quantity(
    *,
    cart: Cart,
    inventory_id: int,
    quantity: Union[int, str, Decimal],
) -> Optional[CartItem]:
    """
    Set absolute quantity.

    NEW RULE:
    - unit_price is the effective wholesale price for the resulting line quantity.
    """
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")

    qty = _to_decimal(quantity)
    if qty < 0:
        raise ValueError("quantity must be >= 0")

    Cart.objects.select_for_update().filter(pk=cart.pk).get()

    if qty == 0:
        deleted, _ = CartItem.objects.filter(
            # cart_id=cart.pk, product_id=product_id
            cart_id=cart.pk,
            inventory_id=inventory_id,
        ).delete()
        if not deleted:
            raise CartItemNotFound("Item not in cart.")
        return None

    item = (
        CartItem.objects.select_for_update()
        .filter(cart_id=cart.pk, inventory_id=inventory_id)
        .first()
    )

    if item is None:
        raise CartItemNotFound("Item not in cart.")

    existing_qty = item.quantity or Decimal("0")

    validate_stock(
        inventory_id=inventory_id,
        requested_total_quantity=qty,
        requested_quantity=qty,
        quantity_in_cart=existing_qty,
        operation="set_quantity",
    )

    wholesale_allowed = _cart_allows_wholesale(cart)
    unit_price = _get_effective_unit_price(
        inventory_id=inventory_id,
        qty=qty,
        wholesale_allowed=wholesale_allowed,
    )

    CartItem.objects.filter(pk=item.pk).update(
        quantity=qty,
        unit_price=unit_price,
        updated_at=_now(),
    )
    item.quantity = qty
    item.unit_price = unit_price
    return item

    


@transaction.atomic
# def cart_remove_item(*, cart: Cart, product_id: int) -> None:
def cart_remove_item(*, cart: Cart, inventory_id: int) -> None:
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")

    Cart.objects.select_for_update().filter(pk=cart.pk).get()
    deleted, _ = CartItem.objects.filter(
        # cart_id=cart.pk, product_id=product_id
        cart_id=cart.pk,
        inventory_id=inventory_id,
    ).delete()
    if not deleted:
        raise CartItemNotFound("Item not in cart.")


# Owner-level wrappers: one service call per endpoint (thin views)
# @transaction.atomic
# def cart_add_item_for_owner(
#     *, owner: CartOwner, product_id: int, quantity: Union[int, str, Decimal]
# ) -> CartItem:
#     cart = cart_get_or_create_active(owner=owner)
#     return cart_add_item(cart=cart, product_id=product_id, quantity=quantity)
@transaction.atomic
def cart_add_item_for_owner(
    *, owner: CartOwner, inventory_id: int, quantity: Union[int, str, Decimal]
) -> CartItem:
    cart = cart_get_or_create_active(owner=owner)
    return cart_add_item(cart=cart, inventory_id=inventory_id, quantity=quantity)


# @transaction.atomic
# def cart_set_item_quantity_for_owner(
#     *, owner: CartOwner, product_id: int, quantity: Union[int, str, Decimal]
# ) -> Optional[CartItem]:
#     cart = cart_get_or_create_active(owner=owner)
#     return cart_set_item_quantity(cart=cart, product_id=product_id, quantity=quantity)
@transaction.atomic
def cart_set_item_quantity_for_owner(
    *, owner: CartOwner, inventory_id: int, quantity: Union[int, str, Decimal]
) -> Optional[CartItem]:
    cart = cart_get_or_create_active(owner=owner)
    return cart_set_item_quantity(
        cart=cart, inventory_id=inventory_id, quantity=quantity
    )


# @transaction.atomic
# def cart_remove_item_for_owner(*, owner: CartOwner, product_id: int) -> None:
#     cart = cart_get_or_create_active(owner=owner)
#     cart_remove_item(cart=cart, product_id=product_id)
@transaction.atomic
def cart_remove_item_for_owner(*, owner: CartOwner, inventory_id: int) -> None:
    cart = cart_get_or_create_active(owner=owner)
    cart_remove_item(cart=cart, inventory_id=inventory_id)


@transaction.atomic
def cart_merge_guest_into_user(*, session_key: str, user_id: int) -> Cart:
    guest_cart = (
        # Added status=CartStatus.ACTIVE
        Cart.objects.select_for_update()
        .filter(session_key=session_key, status=CartStatus.ACTIVE)
        .first()
    )
    # if not guest_cart or guest_cart.status != CartStatus.ACTIVE:
    if not guest_cart:
        return cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    user_cart = cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    # Lock both carts in a stable order (avoid deadlocks)
    cart_ids = sorted([guest_cart.pk, user_cart.pk])
    list(Cart.objects.select_for_update().filter(id__in=cart_ids).order_by("id"))

    guest_items = list(
        CartItem.objects.select_for_update().filter(cart_id=guest_cart.pk)
    )

    touched_inventory_ids: set[int] = set()

    # 1) Merge quantities safely without exceeding current stock.
    for gi in guest_items:
        guest_qty = gi.quantity or Decimal("0")

        if guest_qty <= 0:
            continue

        try:
            inventory = _get_sellable_inventory(inventory_id=gi.inventory_id)
        except ValidationError:
            # Guest item is no longer sellable, so do not merge it.
            continue

        available_stock = Decimal(str(inventory.remaining_quantity or 0))

        if available_stock <= 0:
            continue

        user_item = (
            CartItem.objects.select_for_update()
            .filter(cart_id=user_cart.pk, inventory_id=gi.inventory_id)
            .first()
        )

        existing_qty = user_item.quantity if user_item else Decimal("0")
        requested_total_quantity = existing_qty + guest_qty

        # Never allow the merged cart quantity to exceed stock.
        final_qty = min(requested_total_quantity, available_stock)

        if final_qty <= 0:
            continue

        touched_inventory_ids.add(gi.inventory_id)

        wholesale_allowed = _cart_allows_wholesale(user_cart)
        correct_unit_price = _get_effective_unit_price(
            inventory_id=gi.inventory_id,
            qty=final_qty,
            wholesale_allowed=wholesale_allowed,
        )

        if user_item:
            CartItem.objects.filter(pk=user_item.pk).update(
                quantity=final_qty,
                unit_price=correct_unit_price,
                updated_at=_now(),
            )
            continue

        try:
            CartItem.objects.create(
                cart_id=user_cart.pk,
                inventory_id=gi.inventory_id,
                quantity=final_qty,
                unit_price=correct_unit_price,
            )
        except IntegrityError:
            user_item = (
                CartItem.objects.select_for_update()
                .get(cart_id=user_cart.pk, inventory_id=gi.inventory_id)
            )

            existing_qty = user_item.quantity or Decimal("0")
            requested_total_quantity = existing_qty + guest_qty
            final_qty = min(requested_total_quantity, available_stock)

            correct_unit_price = _get_effective_unit_price(
                inventory_id=gi.inventory_id,
                qty=final_qty,
                wholesale_allowed=wholesale_allowed,
            )

            CartItem.objects.filter(pk=user_item.pk).update(
                quantity=final_qty,
                unit_price=correct_unit_price,
                updated_at=_now(),
            )

    # 2) Normalize unit_price based on FINAL quantities (wholesale tiers)
    user_lines = list(
        CartItem.objects.select_for_update().filter(
            # cart_id=user_cart.pk, product_id__in=touched_product_ids
            cart_id=user_cart.pk,
            inventory_id__in=touched_inventory_ids,
        )
    )

    for line in user_lines:
        final_qty = line.quantity or Decimal("0")
        wholesale_allowed = _cart_allows_wholesale(user_cart)
        correct_unit_price = _get_effective_unit_price(
            inventory_id=line.inventory_id,
            qty=final_qty,
            wholesale_allowed=wholesale_allowed,
        )
        if line.unit_price != correct_unit_price:
            CartItem.objects.filter(pk=line.pk).update(
                unit_price=correct_unit_price,
                updated_at=_now(),
            )

    # 3) delete guest cart items now that they’re merged
    CartItem.objects.filter(cart_id=guest_cart.pk).delete()

    # 4) Mark guest cart merged
    guest_cart.status = CartStatus.MERGED
    guest_cart.merged_into_cart_id = user_cart.pk
    guest_cart.save(update_fields=["status", "merged_into_cart_id", "updated_at"])

    return user_cart


@transaction.atomic
def cart_mark_checked_out(*, cart: Cart) -> Cart:
    now = _now()
    updated = Cart.objects.filter(pk=cart.pk, status=CartStatus.ACTIVE).update(
        status=CartStatus.CHECKED_OUT, updated_at=now
    )
    if updated != 1:
        raise CartNotActive("Only ACTIVE carts can be checked out")

    cart.status = CartStatus.CHECKED_OUT
    cart.updated_at = now
    return cart


def _safe_image_url(product) -> str | None:
    img = getattr(product, "image", None)
    if not img:
        return None

    # If it's a FileField/ImageField, it usually has .url
    url = getattr(img, "url", None)
    if url:
        return url

    # If factory stored a string path/url
    if isinstance(img, str):
        return img

    # Last resort: try string conversion
    try:
        s = str(img)
        return s or None
    except Exception:
        return None


def get_cart_summary(cart) -> dict:
    # qs = cart.items.select_related("product")
    qs = cart.items.select_related(
        "inventory",
        "inventory__product",
        "inventory__product__producer",
    )

    money_field = DecimalField(max_digits=12, decimal_places=2)
    qty_field = DecimalField(max_digits=10, decimal_places=2)

    item_count = qs.count()

    total_quantity = qs.aggregate(
        total=Coalesce(
            Sum("quantity"),
            Value(Decimal("0.00"), output_field=qty_field),
            output_field=qty_field,
        )
    )["total"]

    subtotal = qs.aggregate(
        total=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("unit_price") * F("quantity"),
                    output_field=money_field,
                )
            ),
            Value(Decimal("0.00"), output_field=money_field),
            output_field=money_field,
        )
    )["total"]

    items = []
    for it in qs:
        qty = it.quantity or Decimal("0.00")
        unit_price = it.unit_price or Decimal("0.00")

        product = it.inventory.product
        inventory = it.inventory

        # Product base price (non-wholesale)
        # base_unit_price = getattr(it.product, "price", None)
        base_unit_price = getattr(product, "price", None)
        base_unit_price = (
            Decimal(str(base_unit_price))
            if base_unit_price is not None
            else Decimal("0.00")
        )

        line_total = unit_price * qty
        base_line_total = base_unit_price * qty

        # Savings can be negative if data is weird; clamp later on frontend too
        savings_total = base_line_total - line_total
        savings_per_unit = base_unit_price - unit_price

        items.append(
            {
                "id": it.id,
                "product_id": product.id,
                "inventory_id": inventory.id,
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "unit": getattr(product, "unit", "") or "",
                    "producer_name": getattr(product.producer, "farm_name", None),
                    "image": _safe_image_url(product),
                    "stock_quantity": inventory.remaining_quantity,
                    "base_unit_price": base_unit_price,
                    # Provide the unified discount properties
                    "discount_percentage": inventory.current_discount_percentage,
                    "discount_reason": inventory.current_discount_reason,
                    "surplus_note": inventory.surplus_note,
                },
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total,
                "base_line_total": base_line_total,
                "savings_per_unit": savings_per_unit,
                "savings_total": savings_total,
            }
        )

    total_quantity_out = (
        int(total_quantity)
        if total_quantity == total_quantity.to_integral()
        else str(total_quantity)
    )

    return {
        "items": items,
        "item_count": item_count,
        "total_quantity": total_quantity_out,
        "subtotal": subtotal,
        "currency": "GBP",
    }


def cart_get_cart_summary(*, owner: CartOwner) -> dict:
    """Convenience: resolve active cart for owner and return summary."""
    cart = cart_get_or_create_active(owner=owner)
    return get_cart_summary(cart=cart)
