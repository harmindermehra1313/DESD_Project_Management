from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from carts.models import Cart

from carts.services import (
    CartOwner,
    CartItemNotFound,
    CartNotActive,
    cart_get_or_create_active,
    cart_add_item,
    cart_set_item_quantity,
    cart_remove_item,
    cart_merge_guest_into_user,
)

from carts.api.serializers.carts import (
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
    if request.user.is_authenticated:
        return CartOwner(user_id=request.user.id)
    # Guest: ensure the Django session exists so session_key is not None
    if not request.session.session_key:
        request.session.save()  # generates a session_key

    return CartOwner(session_key=request.session.session_key)


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
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            cart = cart_get_or_create_active(owner=_owner(request))

            cart = (
                Cart.objects.filter(pk=cart.pk)
                .prefetch_related(
                    "items__inventory",
                    "items__inventory__product",
                    "items__inventory__product__producer",
                    "items__inventory__product__inventory_batches",
                )
                .get()
            )
        except Exception as exc:
            raise _translate_service_error(exc)

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemAddView(CreateAPIView):
    permission_classes = [AllowAny]  # AlloweAny / IsAuthenticated
    serializer_class = AddToCartSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)

        ser.is_valid(raise_exception=True)

        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            item = cart_add_item(
                cart=cart,
                # product_id=ser.validated_data["product_id"],
                inventory_id=ser.validated_data["inventory_id"],
                quantity=ser.validated_data["quantity"],
            )
        except Exception as exc:
            print("DEBUG service exception =", repr(exc))
            raise _translate_service_error(exc)

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """
    /cart/items/<pk>/
    pk is treated as product_id.
    """

    permission_classes = [AllowAny]  # AlloweAny / IsAuthenticated

    def patch(self, request, pk: int, *args, **kwargs):
        return self._set_quantity(request, pk)

    def put(self, request, pk: int, *args, **kwargs):
        return self._set_quantity(request, pk)

    def delete(self, request, pk: int, *args, **kwargs):
        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            # cart_remove_item(cart=cart, product_id=int(pk))
            cart_remove_item(cart=cart, inventory_id=int(pk))
        except Exception as exc:
            raise _translate_service_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _set_quantity(self, request, inventory_id: int):
        ser = UpdateQuantitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            cart = cart_get_or_create_active(owner=_owner(request))
            item = cart_set_item_quantity(
                cart=cart,
                # product_id=int(product_id),
                inventory_id=int(inventory_id),
                quantity=ser.validated_data["quantity"],
            )
        except Exception as exc:
            raise _translate_service_error(exc)

        # Service returns None if it removed the line
        if item is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(CartItemSerializer(item).data, status=status.HTTP_200_OK)


class CartMergeAPIView(APIView):
    """
    POST /api/cart/merge/

    Merge the current anonymous session cart into the authenticated user's cart.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Ensure session key exists
        if not request.session.session_key:
            request.session.save()

        session_key = request.session.session_key
        if not session_key:
            return Response(
                {"detail": "No session key found."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cart = cart_merge_guest_into_user(
                session_key=session_key, user_id=request.user.id
            )
        except Exception as exc:
            raise _translate_service_error(exc)

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
