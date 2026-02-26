from decimal import Decimal

import pytest
from django.urls import NoReverseMatch, reverse
from model_bakery import baker
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(transaction=True)


def D(x) -> Decimal:
    return Decimal(str(x))


def rev(name: str, *, kwargs=None) -> str:
    
    for candidate in (f"api:{name}", name):
        try:
            return reverse(candidate, kwargs=kwargs)
        except NoReverseMatch:
            continue
    raise


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()



def test_tc_006_logged_in_add_view_modify_remove_cart(api_client, user):
    """
    TC-006 via HTTP API (logged-in customer).
    Covers:
    - add 2 products
    - view cart contents (me)
    - verify quantities/prices/totals + producer info
    - modify quantity
    - verify updated totals
    - remove item
    - verify counts/totals
    - cart persists (same cart id across calls)
    """

    # Authenticate user (treat as "logged in")
    api_client.force_authenticate(user=user)

    # Multi-vendor setup (producer awareness in cart payload)
    producer_a = baker.make("accounts.Producer", farm_name="Farm A", contact_email="a@farm.test")
    producer_b = baker.make("accounts.Producer", farm_name="Farm B", contact_email="b@farm.test")

    carrots = baker.make(
        "products.Product",
        name="Organic Carrots",
        price=Decimal("2.50"),
        producer=producer_a,
    )
    milk = baker.make(
        "products.Product",
        name="Fresh Milk",
        price=Decimal("1.20"),
        producer=producer_b,
    )

    # Step 1-5: Add carrots qty=2
    url_add = rev("cart-add-item")
    r1 = api_client.post(url_add, {"product_id": carrots.id, "quantity": 2}, format="json")
    assert r1.status_code == 200
    cart_id = r1.data["id"]

    # Treat 200 + returned cart payload as "confirmation"
    assert r1.data["distinct_items"] == 1
    assert r1.data["total_quantity"] == 2
    assert D(r1.data["subtotal"]) == Decimal("5.00")

    # Step 6-9: Add milk qty=3
    r2 = api_client.post(url_add, {"product_id": milk.id, "quantity": 3}, format="json")
    assert r2.status_code == 200
    assert r2.data["id"] == cart_id  # cart persists during browsing session

    # Step 9/10: View cart (cart icon - cart page)
    url_me = rev("cart-me")
    r_me = api_client.get(url_me)
    assert r_me.status_code == 200
    assert r_me.data["id"] == cart_id

    payload = r_me.data
    assert payload["distinct_items"] == 2
    assert payload["total_quantity"] == 5  # 2 + 3

    # Verify items show correct qty + pricing + producer info
    items_by_name = {i["product"]["name"]: i for i in payload["items"]}
    assert set(items_by_name.keys()) == {"Organic Carrots", "Fresh Milk"}

    carrots_item = items_by_name["Organic Carrots"]
    milk_item = items_by_name["Fresh Milk"]

    assert carrots_item["quantity"] == 2
    assert milk_item["quantity"] == 3

    # Producer awareness for multi-vendor cart display
    assert carrots_item["product"]["producer"]["farm_name"] == "Farm A"
    assert milk_item["product"]["producer"]["farm_name"] == "Farm B"

    # Line totals + cart totals
    assert D(carrots_item["unit_price"]) == Decimal("2.50")
    assert D(milk_item["unit_price"]) == Decimal("1.20")

    assert D(carrots_item["line_total"]) == Decimal("2.50") * 2
    assert D(milk_item["line_total"]) == Decimal("1.20") * 3

    expected_subtotal = (Decimal("2.50") * 2) + (Decimal("1.20") * 3)  # 8.60
    assert D(payload["subtotal"]) == expected_subtotal
    assert D(payload["total"]) == expected_subtotal  # serializer aliases total=subtotal

    # Step 11-12: Modify carrots qty -> 3 (absolute set)
    url_set_qty = rev("cart-set-item-quantity", kwargs={"product_id": carrots.id})
    r_patch = api_client.patch(url_set_qty, {"quantity": 3}, format="json")
    assert r_patch.status_code == 200
    assert r_patch.data["id"] == cart_id

    payload2 = r_patch.data
    assert payload2["distinct_items"] == 2
    assert payload2["total_quantity"] == 6  # 3 + 3

    items2 = {i["product"]["name"]: i for i in payload2["items"]}
    assert items2["Organic Carrots"]["quantity"] == 3
    assert items2["Fresh Milk"]["quantity"] == 3

    expected_subtotal2 = (Decimal("2.50") * 3) + (Decimal("1.20") * 3)  # 11.10
    assert D(payload2["subtotal"]) == expected_subtotal2
    assert D(payload2["total"]) == expected_subtotal2

    # Acceptance: remove item from cart
    url_rm = rev("cart-remove-item", kwargs={"product_id": milk.id})
    r_del = api_client.delete(url_rm)
    assert r_del.status_code == 200
    assert r_del.data["id"] == cart_id

    payload3 = r_del.data
    assert payload3["distinct_items"] == 1
    assert payload3["total_quantity"] == 3
    assert {i["product"]["name"] for i in payload3["items"]} == {"Organic Carrots"}
    assert D(payload3["subtotal"]) == Decimal("2.50") * 3

    # Final: cart still retrievable for logged-in user
    r_me2 = api_client.get(url_me)
    assert r_me2.status_code == 200
    assert r_me2.data["id"] == cart_id