from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import IntegrityError
from model_bakery import baker
import uuid

from carts.models import Cart, CartItem, CartStatus
from carts.services import cart_merge_guest_into_user


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def fixed_now(monkeypatch):
    now = datetime(2026, 2, 26, 12, 0, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("carts.services._now", lambda: now)
    return now


def test_merge_no_guest_cart_returns_existing_user_active_cart(user, user_cart):
    new_token = uuid.uuid4()
    assert not Cart.objects.filter(guest_token=new_token).exists()

    got = cart_merge_guest_into_user(guest_token=new_token, user_id=user.id)

    assert got.id == user_cart.id
    assert got.status == CartStatus.ACTIVE


def test_merge_non_active_guest_cart_returns_user_cart_and_does_not_change_guest(user, guest_token):
    guest_cart = Cart.objects.create(
        user=None,
        guest_token=guest_token,
        status=CartStatus.CHECKED_OUT,
    )

    got = cart_merge_guest_into_user(guest_token=guest_token, user_id=user.id)

    assert got.status == CartStatus.ACTIVE
    guest_cart.refresh_from_db()
    assert guest_cart.status == CartStatus.CHECKED_OUT
    assert guest_cart.merged_into_cart_id is None


def test_merge_combines_items_and_marks_guest_merged(user, user_cart, guest_cart, product, fixed_now):
    # user already has product qty=5
    CartItem.objects.create(cart=user_cart, product=product, quantity=5)

    # guest has same product qty=3, plus another product qty=2
    other_product = baker.make("products.Product")
    CartItem.objects.create(cart=guest_cart, product=product, quantity=3)
    CartItem.objects.create(cart=guest_cart, product=other_product, quantity=2)

    got = cart_merge_guest_into_user(guest_token=guest_cart.guest_token, user_id=user.id)
    assert got.id == user_cart.id

    # same product should be incremented (5 + 3)
    item = CartItem.objects.get(cart=user_cart, product=product)
    assert item.quantity == 8
    assert item.updated_at == fixed_now  # updated via QuerySet.update(..., updated_at=_now())

    # other product should be created in user cart
    other_item = CartItem.objects.get(cart=user_cart, product=other_product)
    assert other_item.quantity == 2

    # guest cart should be marked merged and point to user cart
    guest_cart.refresh_from_db()
    assert guest_cart.status == CartStatus.MERGED
    assert guest_cart.merged_into_cart_id == user_cart.id


def test_merge_handles_integrityerror_race_on_create(user, user_cart, guest_cart, fixed_now):
    """
    Force the create() path to raise IntegrityError and ensure the fallback update() path applies.
    """
    race_product = baker.make("products.Product")
    CartItem.objects.create(cart=guest_cart, product=race_product, quantity=4)

    original_create = CartItem.objects.create

    def create_then_raise(*args, **kwargs):
        # Simulate: another txn already created the row with some existing quantity.
        original_create(cart_id=kwargs["cart_id"], product_id=kwargs["product_id"], quantity=1)
        raise IntegrityError("simulate unique constraint race")

    pytest.monkeypatch = pytest.MonkeyPatch()
    pytest.monkeypatch.setattr(CartItem.objects, "create", create_then_raise)

    try:
        got = cart_merge_guest_into_user(guest_token=guest_cart.guest_token, user_id=user.id)
    finally:
        pytest.monkeypatch.undo()

    assert got.id == user_cart.id
    item = CartItem.objects.get(cart=user_cart, product=race_product)
    # existing(1) + guest(4) after fallback update(F("quantity") + gi.quantity)
    assert item.quantity == 5
    assert item.updated_at == fixed_now