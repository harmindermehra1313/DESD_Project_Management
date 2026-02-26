# carts/services.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
import uuid

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Cart, CartItem, CartStatus


Product = apps.get_model("products", "Product")



class CartError(Exception):
    pass


class CartNotFound(CartError):
    pass


class CartNotActive(CartError):
    pass


class CartItemNotFound(CartError):
    pass


@dataclass(frozen=True)
class CartOwner:
    
    user_id: Optional[int] = None
    guest_token: Optional[uuid.UUID] = None


def _now():
    return timezone.now()


def _assert_owner(owner: CartOwner) -> None:
    if bool(owner.user_id) == bool(owner.guest_token):
        raise ValueError("CartOwner must have exactly one of user_id or guest_token set.")


def cart_touch(cart: Cart, *, at=None) -> None:
    
    at = at or _now()
    Cart.objects.filter(pk=cart.pk).update(last_seen_at=at, updated_at=at)



@transaction.atomic
def cart_get_or_create_active(*, owner: CartOwner, guest_ttl_days: int = 14) -> Cart:
    
    _assert_owner(owner)
    now = _now()

    if owner.user_id:
        try:
            cart = (
                Cart.objects.select_for_update()
                .get(user_id=owner.user_id, status=CartStatus.ACTIVE)
            )
            cart_touch(cart, at=now)
            return cart
        except Cart.DoesNotExist:
            pass

        try:
            cart = Cart.objects.create(
                user_id=owner.user_id,
                guest_token=None,
                status=CartStatus.ACTIVE,
                last_seen_at=now,
            )
            return cart
        except IntegrityError:
            # Another transaction created it first.
            cart = (
                Cart.objects.select_for_update()
                .get(user_id=owner.user_id, status=CartStatus.ACTIVE)
            )
            cart_touch(cart, at=now)
            return cart

    # Guest cart
    token = owner.guest_token
    try:
        cart = Cart.objects.select_for_update().get(guest_token=token)
    except Cart.DoesNotExist:
        # Create a new guest cart with the provided token
        expires_at = now + timedelta(days=guest_ttl_days)
        cart = Cart.objects.create(
            user=None,
            guest_token=token,
            status=CartStatus.ACTIVE,
            last_seen_at=now,
            expires_at=expires_at,
        )
        return cart

  
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive(f"Guest cart is not active (status={cart.status}).")
    if cart.expires_at and cart.expires_at <= now:
        cart.status = CartStatus.ABANDONED
        cart.save(update_fields=["status", "updated_at"])
        raise CartNotActive("Guest cart has expired.")

    cart_touch(cart, at=now)
    return cart


def cart_new_guest_token() -> uuid.UUID:
    return uuid.uuid4()



@transaction.atomic
def cart_add_item(*, cart: Cart, product_id: int, quantity: int) -> CartItem:
    """
    Add quantity to an item. If item exists, increment atomically with F(). :contentReference[oaicite:5]{index=5}
    """
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")
    if quantity <= 0:
        raise ValueError("quantity must be > 0")

    # Validate product exists (fast path)
    if not Product.objects.filter(pk=product_id).exists():
        raise ValueError("Invalid product_id")

    # Lock cart row to keep merges/checkout consistent
    Cart.objects.select_for_update().filter(pk=cart.pk).get()

    # Try atomic update first
    updated = (
        CartItem.objects
        .filter(cart_id=cart.pk, product_id=product_id)
        .update(quantity=F("quantity") + quantity, updated_at=_now())
    )
    if updated:
        return CartItem.objects.get(cart_id=cart.pk, product_id=product_id)

    # Create if missing; handle race with UNIQUE(cart, product)
    try:
        return CartItem.objects.create(cart_id=cart.pk, product_id=product_id, quantity=quantity)
    except IntegrityError:
        CartItem.objects.filter(cart_id=cart.pk, product_id=product_id).update(
            quantity=F("quantity") + quantity, updated_at=_now()
        )
        return CartItem.objects.get(cart_id=cart.pk, product_id=product_id)


@transaction.atomic
def cart_set_item_quantity(*, cart: Cart, product_id: int, quantity: int) -> None:
    """
    Set absolute quantity. quantity=0 removes the item.
    """
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")
    if quantity < 0:
        raise ValueError("quantity must be >= 0")

    Cart.objects.select_for_update().filter(pk=cart.pk).get()

    if quantity == 0:
        deleted, _ = CartItem.objects.filter(cart_id=cart.pk, product_id=product_id).delete()
        if not deleted:
            raise CartItemNotFound("Item not in cart.")
        return

    # Validate product exists if we're setting a positive qty
    if not Product.objects.filter(pk=product_id).exists():
        raise ValueError("Invalid product_id")

    updated = CartItem.objects.filter(cart_id=cart.pk, product_id=product_id).update(
        quantity=quantity, updated_at=_now()
    )
    if updated:
        return

    try:
        CartItem.objects.create(cart_id=cart.pk, product_id=product_id, quantity=quantity)
    except IntegrityError:
        CartItem.objects.filter(cart_id=cart.pk, product_id=product_id).update(
            quantity=quantity, updated_at=_now()
        )


@transaction.atomic
def cart_remove_item(*, cart: Cart, product_id: int) -> None:
    if cart.status != CartStatus.ACTIVE:
        raise CartNotActive("Cannot modify a non-active cart.")
    Cart.objects.select_for_update().filter(pk=cart.pk).get()
    deleted, _ = CartItem.objects.filter(cart_id=cart.pk, product_id=product_id).delete()
    if not deleted:
        raise CartItemNotFound("Item not in cart.")



@transaction.atomic
def cart_merge_guest_into_user(
    *,
    guest_token: uuid.UUID,
    user_id: int,
) -> Cart:
   
    guest_cart = Cart.objects.select_for_update().filter(
        guest_token=guest_token
    ).first()
    if not guest_cart:
        # No guest cart - > just return/get user cart
        return cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    if guest_cart.status != CartStatus.ACTIVE:
        return cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    user_cart = cart_get_or_create_active(owner=CartOwner(user_id=user_id))

    # Lock both carts in a stable order
    cart_ids = sorted([guest_cart.pk, user_cart.pk])
    list(Cart.objects.select_for_update().filter(id__in=cart_ids).order_by("id"))

    guest_items = list(
        CartItem.objects.select_for_update().filter(cart_id=guest_cart.pk)
    )

    for gi in guest_items:
        # Try update existing first (atomic increment), else create
        updated = CartItem.objects.filter(
            cart_id=user_cart.pk, product_id=gi.product.pk
        ).update(quantity=F("quantity") + gi.quantity, updated_at=_now())
        if not updated:
            try:
                CartItem.objects.create(
                    cart_id=user_cart.pk, product_id=gi.product.pk, quantity=gi.quantity
                )
            except IntegrityError:
                CartItem.objects.filter(
                    cart_id=user_cart.pk, product_id=gi.product.pk
                ).update(quantity=F("quantity") + gi.quantity, updated_at=_now())

    guest_cart.status = CartStatus.MERGED
    guest_cart.merged_into_cart_id = user_cart.pk
    guest_cart.save(update_fields=["status", "merged_into_cart", "updated_at"])

    return user_cart



@transaction.atomic
def cart_mark_checked_out(*, cart: Cart) -> Cart:
    now = _now()
    updated = (
        Cart.objects
        .filter(pk=cart.pk, status=CartStatus.ACTIVE)
        .update(status=CartStatus.CHECKED_OUT, updated_at = now)
    )
    if updated != 1:
        raise CartNotActive("Only ACTIVE carts can be checked out")

    # keep in-memory instance consistent for callers
    cart.status = CartStatus.CHECKED_OUT
    cart.updated_at = now
    return cart