from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView

from carts.services import (
    CartOwner,
    CartItemNotFound,
    CartNotActive,
    cart_get_or_create_active,
    cart_add_item,
    cart_set_item_quantity,
    cart_remove_item,
)

from api.serializers.carts import (
    AddToCartSerializer,
    UpdateQuantitySerializer,
    CartSerializer,
    CartItemSerializer,
)

def _ensure_session_key(request) -> str:
    """
    Ensures request.session has a usable session_key.
    For guests, the cart is tied to this session_key.
    """
    if not request.session.session_key:
        request.session.save()  # generates a session_key
    return request.session.session_key

def _owner(request) -> CartOwner:
    """
    Auth user -> CartOwner(user_id=...)
    Guest -> CartOwner(session_key=...)
    """
    if request.user and request.user.is_authenticated:
        return CartOwner(user_id=request.user.id)

    return CartOwner(session_key=_ensure_session_key(request))


def _translate_service_error(exc: Exception) -> Exception:
    if isinstance(exc, DjangoValidationError):
        return ValidationError(detail=exc.message)
    if isinstance(exc, CartItemNotFound):
        return NotFound(detail=str(exc) or "Cart item not found.")
    if isinstance(exc, CartNotActive):
        return ValidationError(detail=str(exc) or "Cart is not active.")
    if isinstance(exc, ValueError):
        return ValidationError(detail=str(exc))
    return exc


class CartAPIView(APIView):
    permission_classes = [AllowAny] # AlloweAny / IsAuthenticated 

    def get(self, request, *args, **kwargs):
        try:
            cart = cart_get_or_create_active(owner=_owner(request))
        except Exception as exc:
            raise _translate_service_error(exc)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemAddView(CreateAPIView):
    permission_classes = [AllowAny] # AlloweAny / IsAuthenticated 
    serializer_class = AddToCartSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            item = cart_add_item(
                cart=cart,
                product_id=ser.validated_data["product_id"],
                quantity=ser.validated_data["quantity"],
            )
        except Exception as exc:
            raise _translate_service_error(exc)

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """
    /cart/items/<pk>/
    pk is treated as product_id.
    """
    permission_classes = [AllowAny] # AlloweAny / IsAuthenticated 

    def patch(self, request, pk: int, *args, **kwargs):
        return self._set_quantity(request, pk)

    def put(self, request, pk: int, *args, **kwargs):
        return self._set_quantity(request, pk)

    def delete(self, request, pk: int, *args, **kwargs):
        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            cart_remove_item(cart=cart, product_id=int(pk))
        except Exception as exc:
            raise _translate_service_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _set_quantity(self, request, product_id: int):
        ser = UpdateQuantitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            item = cart_set_item_quantity(
                cart=cart,
                product_id=int(product_id),
                quantity=ser.validated_data["quantity"],
            )
        except Exception as exc:
            raise _translate_service_error(exc)

        # Service returns None if it removed the line
        if item is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(CartItemSerializer(item).data, status=status.HTTP_200_OK)