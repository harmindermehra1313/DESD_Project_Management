
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.apps import apps
from rest_framework import serializers

from carts.models import Cart, CartItem
from carts.services import cart_add_item, cart_remove_item, cart_set_item_quantity


Product = apps.get_model("products", "Product")  


class ProductMiniSerializer(serializers.ModelSerializer):
    """
    Small product payload for cart display:
    - price/unit for calculations
    - producer info for multi-vendor awareness
    """
    producer = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "price", "unit", "image", "producer"]

    def get_producer(self, obj) -> dict[str, Any] | None:
        p = getattr(obj, "producer", None)
        if not p:
            return None
        return {
            "id": getattr(p, "id", None),
            # producer model fields may vary; keep this resilient
            "farm_name": getattr(p, "farm_name", None),
            "contact_email": getattr(p, "contact_email", None),
        }


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductMiniSerializer(read_only=True)
    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        source="product.price",
    )
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "quantity",
            "unit_price",
            "line_total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "unit_price", "line_total", "product"]

    def get_line_total(self, obj: CartItem) -> Decimal:
        price = getattr(obj.product, "price", None)
        if price is None:
            return Decimal("0.00")
        return price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    distinct_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    subtotal = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()  # alias for now (no shipping/tax modeled here)

    class Meta:
        model = Cart
        fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
            "expires_at",
            "distinct_items",
            "total_quantity",
            "subtotal",
            "total",
            "items",
        ]
        read_only_fields = fields

    def _items_qs(self, cart: Cart):
        # Avoid N+1 queries when computing totals / nested product+producer
        return cart.items.select_related("product", "product__producer").all()

    def get_distinct_items(self, obj: Cart) -> int:
        return self._items_qs(obj).count()

    def get_total_quantity(self, obj: Cart) -> int:
        return sum(i.quantity for i in self._items_qs(obj))

    def get_subtotal(self, obj: Cart) -> Decimal:
        total = Decimal("0.00")
        for i in self._items_qs(obj):
            price = getattr(i.product, "price", None) or Decimal("0.00")
            total += price * i.quantity
        return total

    def get_total(self, obj: Cart) -> Decimal:
        # [TODO: Change is later for tax, etc]
        return self.get_subtotal(obj)


# Serializers for TC-006 


class CartAddItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)

    def save(self, **kwargs) -> Cart:
        cart: Cart = self.context["cart"]
        cart_add_item(cart=cart, product_id=self.validated_data["product_id"], quantity=self.validated_data["quantity"])
        cart.refresh_from_db()
        return cart


class CartSetItemQuantitySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=0)  # 0 removes item per service docstring :contentReference[oaicite:2]{index=2}

    def save(self, **kwargs) -> Cart:
        cart: Cart = self.context["cart"]
        cart_set_item_quantity(
            cart=cart,
            product_id=self.validated_data["product_id"],
            quantity=self.validated_data["quantity"],
        )
        cart.refresh_from_db()
        return cart


class CartRemoveItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)

    def save(self, **kwargs) -> Cart:
        cart: Cart = self.context["cart"]
        cart_remove_item(cart=cart, product_id=self.validated_data["product_id"])
        cart.refresh_from_db()
        return cart