import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from model_bakery import baker

from carts.models import Cart, CartStatus
from carts.services import CartOwner, CartNotActive, cart_get_or_create_active


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def fixed_now(monkeypatch):
    """
    Patch carts.services._now() so we can assert last_seen_at/expiry deterministically.
    """
    now = datetime(2026, 2, 26, 12, 0, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("carts.services._now", lambda: now)
    return now


def test_owner_must_have_exactly_one_identifier():
    with pytest.raises(ValueError, match="exactly one"):
        cart_get_or_create_active(owner=CartOwner())

    with pytest.raises(ValueError, match="exactly one"):
        cart_get_or_create_active(owner=CartOwner(user_id=1, guest_token=uuid.uuid4()))


def test_user_owner_returns_existing_active_and_touches(user, fixed_now):
    old = fixed_now - timedelta(days=1)
    existing = baker.make(
        "carts.Cart",
        user=user,
        guest_token=None,
        status=CartStatus.ACTIVE,
        last_seen_at=old,
        expires_at=None,
    )

    got = cart_get_or_create_active(owner=CartOwner(user_id=user.id))
    assert got.id == existing.id

    existing.refresh_from_db()
    assert existing.last_seen_at == fixed_now
    # cart_touch() updates updated_at via queryset.update(...)
    assert existing.updated_at == fixed_now


def test_user_owner_creates_active_when_missing(user, fixed_now):
    got = cart_get_or_create_active(owner=CartOwner(user_id=user.id))

    assert got.user_id == user.id
    assert got.status == CartStatus.ACTIVE
    assert got.guest_token is None
    got.refresh_from_db()
    assert got.last_seen_at == fixed_now


def test_user_owner_ignores_non_active_and_creates_new_active(user, fixed_now):
    old_cart = baker.make(
        "carts.Cart",
        user=user,
        guest_token=None,
        status=CartStatus.CHECKED_OUT,
    )

    got = cart_get_or_create_active(owner=CartOwner(user_id=user.id))
    assert got.status == CartStatus.ACTIVE
    assert got.id != old_cart.id


def test_guest_owner_creates_cart_when_missing(guest_token, fixed_now):
    got = cart_get_or_create_active(
        owner=CartOwner(guest_token=guest_token),
        guest_ttl_days=7,
    )

    assert got.user_id is None
    assert got.guest_token == guest_token
    assert got.status == CartStatus.ACTIVE
    got.refresh_from_db()
    assert got.last_seen_at == fixed_now
    assert got.expires_at == fixed_now + timedelta(days=7)


def test_guest_owner_returns_existing_active_and_touches(guest_token, fixed_now):
    old = fixed_now - timedelta(days=2)
    existing = baker.make(
        "carts.Cart",
        user=None,
        guest_token=guest_token,
        status=CartStatus.ACTIVE,
        last_seen_at=old,
        expires_at=fixed_now + timedelta(days=10),
    )

    got = cart_get_or_create_active(owner=CartOwner(guest_token=guest_token))
    assert got.id == existing.id

    existing.refresh_from_db()
    assert existing.last_seen_at == fixed_now
    assert existing.updated_at == fixed_now


def test_guest_owner_rejects_non_active_guest_cart(guest_token):
    baker.make(
        "carts.Cart",
        user=None,
        guest_token=guest_token,
        status=CartStatus.MERGED,
    )

    with pytest.raises(CartNotActive, match=r"Guest cart is not active"):
        cart_get_or_create_active(owner=CartOwner(guest_token=guest_token))


def test_guest_owner_rejects_expired_guest_cart(guest_token, fixed_now):
    # expires_at <= now triggers expiry path
    baker.make(
        "carts.Cart",
        user=None,
        guest_token=guest_token,
        status=CartStatus.ACTIVE,
        expires_at=fixed_now,
    )

    with pytest.raises(CartNotActive, match="Guest cart has expired"):
        cart_get_or_create_active(owner=CartOwner(guest_token=guest_token))

    # NOTE: Because cart_get_or_create_active is wrapped in transaction.atomic,
    # any DB update done right before raising will be rolled back.
    # So don't assert status changed here unless you change the service behavior.
    cart = Cart.objects.get(guest_token=guest_token)
    assert cart.status == CartStatus.ACTIVE