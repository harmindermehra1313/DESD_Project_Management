from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from carts.services import CartOwner, cart_get_or_create_active




@pytest.fixture
def authenticated_client(user):
    """
    APIClient authenticated as 'user' fixture.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_product(*, name: str, price: Decimal, unit: str, stock: Decimal):
    """
    Safe product factory for this project.
    IMPORTANT: do NOT create Producer (Producer.user is NOT NULL in this DB).
    """
    Product = apps.get_model("products", "Product")

    # Prefer model_bakery if present
    try:
        from model_bakery import baker  # type: ignore

        return baker.make(
            Product,
            name=name,
            price=price,
            unit=unit,
            stock_quantity=stock,
        )
    except Exception:
        pass

    field_names = {f.name for f in Product._meta.get_fields()}
    kwargs = {}
    if "name" in field_names:
        kwargs["name"] = name
    if "price" in field_names:
        kwargs["price"] = price
    if "unit" in field_names:
        kwargs["unit"] = unit
    if "stock_quantity" in field_names:
        kwargs["stock_quantity"] = stock
    if "description" in field_names and "description" not in kwargs:
        kwargs["description"] = f"{name} description"
    if "is_active" in field_names and "is_active" not in kwargs:
        kwargs["is_active"] = True

    # category if present and required-ish
    if "category" in field_names and "category" not in kwargs:
        try:
            Category = apps.get_model("products", "Category")
            cat_field_names = {f.name for f in Category._meta.get_fields()}
            cat_kwargs = {"name": "Test Category"} if "name" in cat_field_names else {}
            kwargs["category"] = Category.objects.create(**cat_kwargs)
        except Exception:
            pass

    return Product.objects.create(**kwargs)


@pytest.fixture
def organic_carrots(db):
    return _make_product(
        name="Organic Carrots",
        price=Decimal("1.50"),
        unit="kg",
        stock=Decimal("100.00"),
    )


@pytest.fixture
def fresh_milk(db):
    return _make_product(
        name="Fresh Milk",
        price=Decimal("0.80"),
        unit="litre",
        stock=Decimal("100.00"),
    )


@pytest.fixture
def active_cart(user, db):
    """
    Active cart for logged-in user via service layer.
    """
    owner = CartOwner(user_id=user.id)
    return cart_get_or_create_active(owner=owner)


# ---------- Backwards-compatibility layer ----------
# These fixtures are what your existing test suite is asking for.
# If your original conftest already defines them, DELETE these aliases.


@pytest.fixture
def user(db):
    """
    Ensure a user fixture exists with required email field.
    If your original conftest already has 'user', keep that one instead.
    """
    User = get_user_model()
    field_names = {f.name for f in User._meta.get_fields()}

    kwargs = {"email": "user@example.com", "password": "pass12345"}
    if "username" in field_names:
        kwargs["username"] = "user"

    return User.objects.create_user(**kwargs)


@pytest.fixture
def user_cart(active_cart):
    """
    Alias: many unit tests expect 'user_cart'.
    """
    return active_cart


@pytest.fixture
def product(db):
    """
    Alias: many unit tests expect a generic 'product'.
    """
    return _make_product(
        name="Test Product",
        price=Decimal("2.00"),
        unit="kg",
        stock=Decimal("100.00"),
    )


@pytest.fixture
def session_key():
    """
    Alias: used by guest-cart tests.
    """
    return "test-session-key-123"


@pytest.fixture
def guest_cart(db, session_key):
    """
    Guest active cart via service layer.
    """
    owner = CartOwner(session_key=session_key)
    return cart_get_or_create_active(owner=owner)
