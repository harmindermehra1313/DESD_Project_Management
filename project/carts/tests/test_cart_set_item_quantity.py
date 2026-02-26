from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import IntegrityError

from carts.models import CartItem, CartStatus
from carts.services import CartItemNotFound, CartNotActive, cart_set_item_quantity


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def fixed_now(monkeypatch):
    """
    Patch carts.services._now() so updated_at assertions are deterministic.
    """
    now = datetime(2026, 2, 26, 12, 0, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("carts.services._now", lambda: now)
    return now


def test_set_item_quantity_creates_item_when_missing(user_cart, product):
    cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=3)

    item = CartItem.objects.get(cart=user_cart, product=product)
    assert item.quantity == 3


def test_set_item_quantity_updates_existing_item_absolute(user_cart, product, fixed_now):
    # create
    CartItem.objects.create(cart=user_cart, product=product, quantity=7)

    # update to absolute qty (not increment)
    cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=2)

    item = CartItem.objects.get(cart=user_cart, product=product)
    assert item.quantity == 2
    assert item.updated_at == fixed_now


def test_set_item_quantity_quantity_zero_removes_item(user_cart, product):
    CartItem.objects.create(cart=user_cart, product=product, quantity=5)

    cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=0)

    assert not CartItem.objects.filter(cart=user_cart, product=product).exists()


def test_set_item_quantity_quantity_zero_raises_if_missing(user_cart, product):
    with pytest.raises(CartItemNotFound, match="Item not in cart"):
        cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=0)


@pytest.mark.parametrize("bad_qty", [-1, -10])
def test_set_item_quantity_rejects_negative_quantity(user_cart, product, bad_qty):
    with pytest.raises(ValueError, match=r"quantity must be >= 0"):
        cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=bad_qty)


def test_set_item_quantity_rejects_invalid_product_id_when_positive(user_cart):
    with pytest.raises(ValueError, match="Invalid product_id"):
        cart_set_item_quantity(cart=user_cart, product_id=999999999, quantity=1)


def test_set_item_quantity_rejects_non_active_cart(user_cart, product):
    user_cart.status = CartStatus.CHECKED_OUT
    user_cart.save(update_fields=["status"])

    with pytest.raises(CartNotActive, match="Cannot modify a non-active cart"):
        cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=1)


def test_set_item_quantity_handles_race_integrityerror(user_cart, product, monkeypatch, fixed_now):
    """
    Simulate: update() returns 0 (item not found), but create() "races" and another txn creates first.
    We emulate this by creating the row inside a patched create() and then raising IntegrityError.
    """
    original_create = CartItem.objects.create

    def create_then_raise(*args, **kwargs):
        original_create(*args, **kwargs)  # row now exists
        raise IntegrityError("simulate unique constraint race")

    monkeypatch.setattr(CartItem.objects, "create", create_then_raise)

    cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=9)

    item = CartItem.objects.get(cart=user_cart, product=product)
    assert item.quantity == 9
    assert item.updated_at == fixed_now