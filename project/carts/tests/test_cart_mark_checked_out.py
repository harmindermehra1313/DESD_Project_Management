from datetime import datetime, timezone as dt_timezone

import pytest

from carts.models import CartStatus
from carts.services import CartNotActive, cart_mark_checked_out


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def fixed_now(monkeypatch):
    now = datetime(2026, 2, 26, 12, 0, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("carts.services._now", lambda: now)
    return now


def test_cart_mark_checked_out_sets_status_and_updated_at(user_cart, fixed_now):
    # precondition
    user_cart.refresh_from_db()
    assert user_cart.status == CartStatus.ACTIVE

    cart_mark_checked_out(cart=user_cart)

    user_cart.refresh_from_db()
    assert user_cart.status == CartStatus.CHECKED_OUT
    assert user_cart.updated_at == fixed_now


@pytest.mark.parametrize("bad_status", [CartStatus.MERGED, CartStatus.CHECKED_OUT, CartStatus.ABANDONED])
def test_cart_mark_checked_out_rejects_non_active_cart(user_cart, bad_status):
    user_cart.status = bad_status
    user_cart.save(update_fields=["status"])

    with pytest.raises(CartNotActive, match="Only ACTIVE carts can be checked out"):
        cart_mark_checked_out(cart=user_cart)

    user_cart.refresh_from_db()
    assert user_cart.status == bad_status


def test_cart_mark_checked_out_is_not_idempotent(user_cart):
    cart_mark_checked_out(cart=user_cart)

    with pytest.raises(CartNotActive):
        cart_mark_checked_out(cart=user_cart)