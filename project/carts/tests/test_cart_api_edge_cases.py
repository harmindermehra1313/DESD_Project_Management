# carts/tests/test_cart_api_edge_cases.py
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def _dec(v) -> Decimal:
    return Decimal(str(v))


def test_add_same_product_twice_merges_quantity(authenticated_client, organic_carrots):
    """
    Add same product twice -> merges quantity (single CartItem).
    """
    r1 = authenticated_client.post(
        "/api/cart/items/",
        data={"product_id": organic_carrots.id, "quantity": "1.00"},
        format="json",
    )
    assert r1.status_code == status.HTTP_201_CREATED, r1.data

    r2 = authenticated_client.post(
        "/api/cart/items/",
        data={"product_id": organic_carrots.id, "quantity": "2.00"},
        format="json",
    )
    # Some implementations return 201 even when it merged; keep it strict to your current behavior
    assert r2.status_code == status.HTTP_201_CREATED, r2.data

    rc = authenticated_client.get("/api/cart/")
    assert rc.status_code == status.HTTP_200_OK, rc.data

    assert rc.data["item_count"] == 1
    assert len(rc.data["items"]) == 1

    item = rc.data["items"][0]
    assert item["product_id"] == organic_carrots.id
    assert _dec(item["quantity"]) == _dec("3.00")

    assert _dec(item["unit_price"]) == _dec(organic_carrots.price)

    expected_line_total = _dec(organic_carrots.price) * _dec("3.00")
    assert _dec(item["line_total"]) == expected_line_total
    assert _dec(rc.data["total_price"]) == expected_line_total


def test_set_quantity_to_zero_removes_item(authenticated_client, organic_carrots):
    """
    Set quantity=0 -> API removes line and returns 204 No Content (your current behavior).
    """
    r = authenticated_client.post(
        "/api/cart/items/",
        data={"product_id": organic_carrots.id, "quantity": "2.00"},
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED, r.data

    r = authenticated_client.patch(
        f"/api/cart/items/{organic_carrots.id}/",
        data={"quantity": "0.00"},
        format="json",
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT
    # DRF Response for 204 has no body
    assert not getattr(r, "data", None)

    rc = authenticated_client.get("/api/cart/")
    assert rc.status_code == status.HTTP_200_OK, rc.data
    assert rc.data["item_count"] == 0
    assert rc.data["items"] == []
    assert _dec(rc.data["total_price"]) == _dec("0.00")


def test_unauthenticated_access_is_403(db):
    """
    Unauthenticated access -> 403 Forbidden (your current behavior).
    (401 would be typical for token auth; 403 is common for session auth + CSRF / permission handling.)
    """
    client = APIClient()

    r = client.get("/api/cart/")
    assert r.status_code == status.HTTP_403_FORBIDDEN

    r = client.post("/api/cart/items/", data={"product_id": 1, "quantity": "1.00"}, format="json")
    assert r.status_code == status.HTTP_403_FORBIDDEN

    r = client.patch("/api/cart/items/1/", data={"quantity": "1.00"}, format="json")
    assert r.status_code == status.HTTP_403_FORBIDDEN


def test_add_non_existent_product_is_400(authenticated_client):
    """
    Non-existent product -> serializer rejects product_id as invalid (400) in your current API.
    """
    r = authenticated_client.post(
        "/api/cart/items/",
        data={"product_id": 99999999, "quantity": "1.00"},
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    # Your API returns a list of DRF ErrorDetail values.
    assert "Invalid product_id" in str(r.data)


def test_set_quantity_non_existent_product_is_400(authenticated_client):
    """
    Non-existent product on update -> serializer rejects product_id (400) in your current API.
    """
    r = authenticated_client.patch(
        "/api/cart/items/99999999/",
        data={"quantity": "1.00"},
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid product_id" in str(r.data)