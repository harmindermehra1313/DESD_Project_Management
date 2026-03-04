import pytest
from model_bakery import baker

from carts.models import CartItem, CartStatus
from carts.services import CartItemNotFound, CartNotActive, cart_remove_item

pytestmark = pytest.mark.django_db(transaction=True)


def test_cart_remove_item_deletes_existing_item(user_cart, product):
    CartItem.objects.create(cart=user_cart, product=product, quantity=2)

    cart_remove_item(cart=user_cart, product_id=product.id)

    assert not CartItem.objects.filter(cart=user_cart, product=product).exists()


def test_cart_remove_item_only_deletes_target_product(user_cart, product):
    other_product = baker.make("products.Product")
    CartItem.objects.create(cart=user_cart, product=product, quantity=2)
    CartItem.objects.create(cart=user_cart, product=other_product, quantity=5)

    cart_remove_item(cart=user_cart, product_id=product.id)

    assert not CartItem.objects.filter(cart=user_cart, product=product).exists()
    assert CartItem.objects.filter(cart=user_cart, product=other_product).exists()


def test_cart_remove_item_raises_if_item_missing(user_cart, product):
    with pytest.raises(CartItemNotFound, match="Item not in cart"):
        cart_remove_item(cart=user_cart, product_id=product.id)


def test_cart_remove_item_rejects_non_active_cart(user_cart, product):
    user_cart.status = CartStatus.CHECKED_OUT
    user_cart.save(update_fields=["status"])

    with pytest.raises(CartNotActive, match="Cannot modify a non-active cart"):
        cart_remove_item(cart=user_cart, product_id=product.id)