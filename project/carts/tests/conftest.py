# shared fixtures/helpers

import uuid
import pytest
from model_bakery import baker

from carts.services import CartOwner, cart_get_or_create_active

@pytest.fixture
def user():
    return baker.make("accounts.User")

@pytest.fixture
def product():
    return baker.make("products.Product")


@pytest.fixture
def user_cart(user):
    return cart_get_or_create_active(owner=CartOwner(user_id=user.id))


@pytest.fixture
def guest_token():
    return uuid.uuid4()


@pytest.fixture
def guest_cart(guest_token):
    return cart_get_or_create_active(owner=CartOwner(guest_token=guest_token))