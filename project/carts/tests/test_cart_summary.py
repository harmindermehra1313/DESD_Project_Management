# carts/tests/test_cart_summary.py
from decimal import Decimal

import pytest
from model_bakery import baker

from carts.services import cart_add_item, cart_set_item_quantity, get_cart_summary


pytestmark = pytest.mark.django_db


def _set_product_stock_and_price(product, *, stock: int, price: Decimal) -> None:
    # Make these tests independent from whatever defaults the Product model has.
    product.stock_quantity = stock
    product.price = price
    product.save(update_fields=["stock_quantity", "price"])


def test_get_cart_summary_empty_cart(user_cart):
    summary = get_cart_summary(cart=user_cart)

    assert summary["items"] == []
    assert summary["item_count"] == 0
    assert summary["subtotal"] == Decimal("0.00")
    assert summary["currency"] == "GBP"


def test_get_cart_summary_single_item_totals(user_cart, product):
    _set_product_stock_and_price(product, stock=100, price=Decimal("9.99"))

    cart_add_item(cart=user_cart, product_id=product.id, quantity=2)

    summary = get_cart_summary(cart=user_cart)

    assert summary["item_count"] == 1
    assert summary["currency"] == "GBP"
    assert summary["subtotal"] == Decimal("19.98")

    assert len(summary["items"]) == 1
    item = summary["items"][0]
    assert item["product_id"] == product.id
    assert item["quantity"] == 2
    assert item["unit_price"] == Decimal("9.99")
    assert item["line_total"] == Decimal("19.98")


def test_get_cart_summary_multi_item_totals(user_cart, product):
    _set_product_stock_and_price(product, stock=100, price=Decimal("10.00"))
    other_product = baker.make("products.Product", stock_quantity=100, price=Decimal("2.50"))

    cart_add_item(cart=user_cart, product_id=product.id, quantity=3)        # 3 * 10.00 = 30.00
    cart_add_item(cart=user_cart, product_id=other_product.id, quantity=4)  # 4 * 2.50 = 10.00

    summary = get_cart_summary(cart=user_cart)

    assert summary["item_count"] == 2
    assert summary["currency"] == "GBP"
    assert summary["subtotal"] == Decimal("40.00")

    by_pid = {i["product_id"]: i for i in summary["items"]}
    assert by_pid[product.id]["quantity"] == 3
    assert by_pid[product.id]["unit_price"] == Decimal("10.00")
    assert by_pid[product.id]["line_total"] == Decimal("30.00")

    assert by_pid[other_product.id]["quantity"] == 4
    assert by_pid[other_product.id]["unit_price"] == Decimal("2.50")
    assert by_pid[other_product.id]["line_total"] == Decimal("10.00")


def test_get_cart_summary_quantity_update_recalculates_correctly(user_cart, product):
    _set_product_stock_and_price(product, stock=100, price=Decimal("7.50"))
    other_product = baker.make("products.Product", stock_quantity=100, price=Decimal("1.25"))

    cart_add_item(cart=user_cart, product_id=product.id, quantity=2)        # 2 * 7.50 = 15.00
    cart_add_item(cart=user_cart, product_id=other_product.id, quantity=8)  # 8 * 1.25 = 10.00

    # Update absolute qty for product: 2 -> 5 (should become 5 * 7.50 = 37.50)
    cart_set_item_quantity(cart=user_cart, product_id=product.id, quantity=5)

    summary = get_cart_summary(cart=user_cart)

    assert summary["item_count"] == 2
    assert summary["subtotal"] == Decimal("47.50")  # 37.50 + 10.00

    by_pid = {i["product_id"]: i for i in summary["items"]}
    assert by_pid[product.id]["quantity"] == 5
    assert by_pid[product.id]["unit_price"] == Decimal("7.50")
    assert by_pid[product.id]["line_total"] == Decimal("37.50")

    assert by_pid[other_product.id]["quantity"] == 8
    assert by_pid[other_product.id]["unit_price"] == Decimal("1.25")
    assert by_pid[other_product.id]["line_total"] == Decimal("10.00")