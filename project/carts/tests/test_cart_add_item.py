import pytest

from carts.models import CartItem, CartStatus
from carts.services import cart_add_item, CartNotActive


pytestmark = pytest.mark.django_db


def test_cart_add_item_creates_new_item(user_cart, product):
    item = cart_add_item(cart=user_cart, product_id=product.id, quantity=2)

    assert item.cart_id == user_cart.id
    assert item.product_id == product.id
    assert item.quantity == 2

    assert CartItem.objects.filter(cart=user_cart, product=product).count() == 1


def test_cart_add_item_increments_existing_item(user_cart, product):
    cart_add_item(cart=user_cart, product_id=product.id, quantity=2)
    item2 = cart_add_item(cart=user_cart, product_id=product.id, quantity=3)

    assert CartItem.objects.filter(cart=user_cart, product=product).count() == 1
    assert item2.quantity == 5

    db_item = CartItem.objects.get(cart=user_cart, product=product)
    assert db_item.quantity == 5


@pytest.mark.parametrize("bad_qty", [0, -1, -5])
def test_cart_add_item_rejects_non_positive_quantity(user_cart, product, bad_qty):
    with pytest.raises(ValueError, match="quantity must be > 0"):
        cart_add_item(cart=user_cart, product_id=product.id, quantity=bad_qty)


def test_cart_add_item_rejects_invalid_product_id(user_cart):
    with pytest.raises(ValueError, match="Invalid product_id"):
        cart_add_item(cart=user_cart, product_id=999999999, quantity=1)


def test_cart_add_item_rejects_non_active_cart(user_cart, product):
    user_cart.status = CartStatus.CHECKED_OUT
    user_cart.save(update_fields=["status"])

    with pytest.raises(CartNotActive, match="Cannot modify a non-active cart"):
        cart_add_item(cart=user_cart, product_id=product.id, quantity=1)


def test_cart_add_item_works_for_guest_cart(guest_cart, product):
    item = cart_add_item(cart=guest_cart, product_id=product.id, quantity=4)
    assert item.cart_id == guest_cart.id
    assert item.product_id == product.id
    assert item.quantity == 4