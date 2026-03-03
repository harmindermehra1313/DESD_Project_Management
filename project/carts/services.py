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
WholesalePrice = apps.get_model("products", "WholesalePrice")


class CartError(Exception):
    """Base domain exception for cart operations."""

    pass


class CartNotFound(CartError):
    pass


class CartNotActive(CartError):
    pass


class CartItemNotFound(CartError):
    pass


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


def _assert_owner(owner: CartOwner) -> None:
    # Exactly one must be set
    if bool(owner.user_id) == bool(owner.session_key):
        raise ValueError(
            "CartOwner must have exactly one of user_id or session_key set."
        )


def _get_product_data(*, product_id: int) -> tuple[Decimal, Decimal]:
    """
    Returns (price, stock_quantity) for the product_id.

    Raises ValueError for invalid product_id.
    """
    row = (
        Product.objects.filter(pk=product_id)
        .values_list("price", "stock_quantity")
        .first()
    )
    if row is None:
        raise ValueError("Invalid product_id")
    price, stock = row
    return Decimal(str(price)), Decimal(str(stock))


def _get_effective_unit_price(*, product_id: int, qty: Decimal) -> Decimal:
    """
    Base price is Product.price.
    If WholesalePrice exists for qty, use the best tier (highest min_quantity <= qty).
    """
    base_price, _stock = _get_product_data(product_id=product_id)

    # WholesalePrice.min_quantity is int, so compare using an int qty
    qty_int = int(qty)  # qty is already >= 0 in callers

    tier_price = (
        WholesalePrice.objects.filter(product_id=product_id, min_quantity__lte=qty_int)
        .order_by("-min_quantity")
        .values_list("unit_price", flat=True)
        .first()
    )

    return base_price if tier_price is None else Decimal(str(tier_price))


def cart_new_session_key() -> str:
    # Session-like token; store as string
    return uuid.uuid4().hex


def cart_touch(cart: Cart, *, at=None) -> None:
    at = at or _now()
    Cart.objects.filter(pk=cart.pk).update(last_seen_at=at, updated_at=at)


def validate_stock(*, product_id: int, requested_quantity: Decimal) -> None:
    _, stock = _get_product_data(product_id=product_id)

    if stock <= 0:
        raise ValidationError("This product is out of stock.")

    if stock < requested_quantity:
        raise ValidationError(f"Only {stock} left in stock.")


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
    *, cart: Cart, product_id: int, quantity: Union[int, str, Decimal]
) -> CartItem:
    """
    Add quantity to an item.

    NEW RULE:
    - unit_price is the effective wholesale price for the resulting line quantity.
    - so if qty crosses a tier, unit_price changes.
    """
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")

    add_qty = _to_decimal(quantity)
    if add_qty <= 0:
        raise ValueError("quantity must be > 0")

    # Lock cart row to keep merges/checkout consistent
    Cart.objects.select_for_update().filter(pk=cart.pk).get()

    # Lock item row (if exists) to safely compute resulting qty
    item = (
        CartItem.objects.select_for_update()
        .filter(cart_id=cart.pk, product_id=product_id)
        .first()
    )

    existing_qty = item.quantity if item else Decimal("0")
    new_qty = existing_qty + add_qty

    validate_stock(product_id=product_id, requested_quantity=new_qty)

    # Compute correct unit price for the resulting qty (server-side truth)
    unit_price = _get_effective_unit_price(product_id=product_id, qty=new_qty)

    if item:
        # Update both quantity and unit_price (tier-aware)
        CartItem.objects.filter(pk=item.pk).update(
            quantity=new_qty,
            unit_price=unit_price,
            updated_at=_now(),
        )
        item.quantity = new_qty
        item.unit_price = unit_price
        return item

    # Create new line with effective unit_price
    try:
        return CartItem.objects.create(
            cart_id=cart.pk,
            product_id=product_id,
            quantity=new_qty,
            unit_price=unit_price,
        )
    except IntegrityError:
        # Race: someone created; lock and update properly
        item = CartItem.objects.select_for_update().get(
            cart_id=cart.pk, product_id=product_id
        )
        new_qty = (item.quantity or Decimal("0")) + add_qty
        validate_stock(product_id=product_id, requested_quantity=new_qty)
        unit_price = _get_effective_unit_price(product_id=product_id, qty=new_qty)

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
    *, cart: Cart, product_id: int, quantity: Union[int, str, Decimal]
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
            cart_id=cart.pk, product_id=product_id
        ).delete()
        if not deleted:
            raise CartItemNotFound("Item not in cart.")
        return None

    validate_stock(product_id=product_id, requested_quantity=qty)

    unit_price = _get_effective_unit_price(product_id=product_id, qty=qty)

    item = (
        CartItem.objects.select_for_update()
        .filter(cart_id=cart.pk, product_id=product_id)
        .first()
    )

    if item:
        CartItem.objects.filter(pk=item.pk).update(
            quantity=qty,
            unit_price=unit_price,
            updated_at=_now(),
        )
        item.quantity = qty
        item.unit_price = unit_price
        return item

    try:
        return CartItem.objects.create(
            cart_id=cart.pk,
            product_id=product_id,
            quantity=qty,
            unit_price=unit_price,
        )
    except IntegrityError:
        item = CartItem.objects.select_for_update().get(
            cart_id=cart.pk, product_id=product_id
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
def cart_remove_item(*, cart: Cart, product_id: int) -> None:
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")

    Cart.objects.select_for_update().filter(pk=cart.pk).get()
    deleted, _ = CartItem.objects.filter(
        cart_id=cart.pk, product_id=product_id
    ).delete()
    if not deleted:
        raise CartItemNotFound("Item not in cart.")


# Owner-level wrappers: one service call per endpoint (thin views)
@transaction.atomic
def cart_add_item_for_owner(
    *, owner: CartOwner, product_id: int, quantity: Union[int, str, Decimal]
) -> CartItem:
    cart = cart_get_or_create_active(owner=owner)
    return cart_add_item(cart=cart, product_id=product_id, quantity=quantity)


@transaction.atomic
def cart_set_item_quantity_for_owner(
    *, owner: CartOwner, product_id: int, quantity: Union[int, str, Decimal]
) -> Optional[CartItem]:
    cart = cart_get_or_create_active(owner=owner)
    return cart_set_item_quantity(cart=cart, product_id=product_id, quantity=quantity)


@transaction.atomic
def cart_remove_item_for_owner(*, owner: CartOwner, product_id: int) -> None:
    cart = cart_get_or_create_active(owner=owner)
    cart_remove_item(cart=cart, product_id=product_id)


@transaction.atomic
def cart_merge_guest_into_user(*, session_key: str, user_id: int) -> Cart:
    guest_cart = (
        Cart.objects.select_for_update().filter(session_key=session_key).first()
    )
    if not guest_cart or guest_cart.status != CartStatus.ACTIVE:
        return cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    user_cart = cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    # Lock both carts in a stable order (avoid deadlocks)
    cart_ids = sorted([guest_cart.pk, user_cart.pk])
    list(Cart.objects.select_for_update().filter(id__in=cart_ids).order_by("id"))

    guest_items = list(
        CartItem.objects.select_for_update().filter(cart_id=guest_cart.pk)
    )

    touched_product_ids: set[int] = set()

    # 1) Merge quantities
    for gi in guest_items:
        touched_product_ids.add(gi.product_id)

        updated = CartItem.objects.filter(
            cart_id=user_cart.pk, product_id=gi.product_id
        ).update(
            quantity=F("quantity") + gi.quantity,
            updated_at=_now(),
        )

        if not updated:
            try:
                CartItem.objects.create(
                    cart_id=user_cart.pk,
                    product_id=gi.product_id,
                    quantity=gi.quantity,
                    unit_price=gi.unit_price,  # temporary; normalized below
                )
            except IntegrityError:
                CartItem.objects.filter(
                    cart_id=user_cart.pk, product_id=gi.product_id
                ).update(
                    quantity=F("quantity") + gi.quantity,
                    updated_at=_now(),
                )

    # 2) Normalize unit_price based on FINAL quantities (wholesale tiers)
    user_lines = list(
        CartItem.objects.select_for_update().filter(
            cart_id=user_cart.pk, product_id__in=touched_product_ids
        )
    )

    for line in user_lines:
        final_qty = line.quantity or Decimal("0")
        correct_unit_price = _get_effective_unit_price(
            product_id=line.product_id,
            qty=final_qty,
        )
        if line.unit_price != correct_unit_price:
            CartItem.objects.filter(pk=line.pk).update(
                unit_price=correct_unit_price,
                updated_at=_now(),
            )

    # 3) OPTIONAL CLEANUP: delete guest cart items now that they’re merged
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
    qs = cart.items.select_related("product")

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

        # Product base price (non-wholesale)
        base_unit_price = getattr(it.product, "price", None)
        base_unit_price = (
            Decimal(str(base_unit_price)) if base_unit_price is not None else Decimal("0.00")
        )

        line_total = unit_price * qty
        base_line_total = base_unit_price * qty

        # Savings can be negative if data is weird; clamp later on frontend too
        savings_total = base_line_total - line_total
        savings_per_unit = base_unit_price - unit_price

        items.append(
            {
                "id": it.id,
                "product_id": it.product_id,
                "product": {
                    "id": it.product_id,
                    "name": it.product.name,
                    "unit": getattr(it.product, "unit", "") or "",
                    "producer_name": getattr(it.product, "producer_name", "") or "",
                    "image": _safe_image_url(it.product),
                    "stock_quantity": getattr(it.product, "stock_quantity", None),

                    # for professional UI
                    "base_unit_price": base_unit_price,
                },
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total,

                # useful for UI/analytics
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
