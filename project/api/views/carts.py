from __future__ import annotations

import uuid

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from carts.services import (
    CartItemNotFound,
    CartNotActive,
    CartOwner,
    cart_get_or_create_active,
    cart_mark_checked_out,
    cart_merge_guest_into_user,
    cart_new_guest_token,
)
from api.serializers.carts import (  
    CartAddItemSerializer,
    CartRemoveItemSerializer,
    CartSerializer,
    CartSetItemQuantitySerializer,
)


class CartViewSet(viewsets.ViewSet):
    """
    Single-cart endpoints (user cart or guest cart).
    Uses service layer for all mutations.
    """

    permission_classes = [AllowAny]

    def get_permissions(self):
        # Only merge requires authenticated user explicitly
        if getattr(self, "action", None) in {"merge_guest"}:
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def list(self, request):
        # Make /api/cart/ behave like “get my current cart”
        return self.me(request)

    def _parse_guest_token(self, request) -> uuid.UUID:
        token_str = (
            request.headers.get("X-Guest-Token")
            or request.query_params.get("guest_token")
        )
        if not token_str:
            raise ValidationError(
                {"guest_token": "Provide X-Guest-Token header (or ?guest_token=...)." }
            )
        try:
            return uuid.UUID(str(token_str))
        except ValueError as e:
            raise ValidationError({"guest_token": "Invalid UUID."}) from e

    def _get_owner(self, request) -> CartOwner:
        if request.user and request.user.is_authenticated:
            return CartOwner(user_id=request.user.id)
        return CartOwner(guest_token=self._parse_guest_token(request))

    def _serialize_cart(self, cart):
        return CartSerializer(cart).data

    def _handle_cart_error(self, exc: Exception):
        # Map service-layer errors to HTTP responses
        if isinstance(exc, CartItemNotFound):
            raise NotFound(str(exc))
        if isinstance(exc, CartNotActive):
            raise ValidationError({"cart": str(exc)})
        if isinstance(exc, ValueError):
            raise ValidationError({"detail": str(exc)})
        raise exc

    @action(detail=False, methods=["post"], url_path="guest-token")
    def guest_token(self, request):
        """
        Create a guest token + active guest cart.
        Client should store token and send it as X-Guest-Token on subsequent calls.
        """
        token = cart_new_guest_token()
        cart = cart_get_or_create_active(owner=CartOwner(guest_token=token))
        payload = self._serialize_cart(cart)
        payload["guest_token"] = str(token)
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """
        Return the active cart for the authenticated user, or the guest cart if anonymous.
        """
        owner = self._get_owner(request)
        try:
            cart = cart_get_or_create_active(owner=owner)
        except Exception as exc:
            self._handle_cart_error(exc)
        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="items")
    def add_item(self, request):
        """
        Add an item to cart (increments quantity if exists).
        Body: { product_id, quantity }
        """
        owner = self._get_owner(request)
        try:
            cart = cart_get_or_create_active(owner=owner)
            ser = CartAddItemSerializer(data=request.data, context={"cart": cart})
            ser.is_valid(raise_exception=True)
            cart = ser.save()
        except Exception as exc:
            self._handle_cart_error(exc)

        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["patch"],
        url_path=r"items/(?P<product_id>\d+)",
    )
    def set_item_quantity(self, request, product_id: str):
        """
        Set absolute item quantity (0 removes).
        Body: { quantity }
        """
        owner = self._get_owner(request)
        try:
            cart = cart_get_or_create_active(owner=owner)
            ser = CartSetItemQuantitySerializer(
                data={"product_id": int(product_id), "quantity": request.data.get("quantity")},
                context={"cart": cart},
            )
            ser.is_valid(raise_exception=True)
            cart = ser.save()
        except Exception as exc:
            self._handle_cart_error(exc)

        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"items/(?P<product_id>\d+)",
    )
    def remove_item(self, request, product_id: str):
        """
        Remove item from cart.
        """
        owner = self._get_owner(request)
        try:
            cart = cart_get_or_create_active(owner=owner)
            ser = CartRemoveItemSerializer(
                data={"product_id": int(product_id)},
                context={"cart": cart},
            )
            ser.is_valid(raise_exception=True)
            cart = ser.save()
        except Exception as exc:
            self._handle_cart_error(exc)

        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request):
        """
        Mark active cart as CHECKED_OUT.
        """
        owner = self._get_owner(request)
        try:
            cart = cart_get_or_create_active(owner=owner)
            cart = cart_mark_checked_out(cart=cart)
            cart.refresh_from_db()
        except Exception as exc:
            self._handle_cart_error(exc)

        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="merge-guest")
    def merge_guest(self, request):
        """
        Merge a guest cart into the authenticated user's active cart.
        Body: { guest_token }
        """
        guest_token = request.data.get("guest_token")
        if not guest_token:
            raise ValidationError({"guest_token": "This field is required."})
        try:
            token = uuid.UUID(str(guest_token))
        except ValueError as e:
            raise ValidationError({"guest_token": "Invalid UUID."}) from e

        try:
            cart = cart_merge_guest_into_user(guest_token=token, user_id=request.user.id)
            cart.refresh_from_db()
        except Exception as exc:
            self._handle_cart_error(exc)

        return Response(self._serialize_cart(cart), status=status.HTTP_200_OK)