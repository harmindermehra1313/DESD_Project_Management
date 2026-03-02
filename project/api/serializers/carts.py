from __future__ import annotations

from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers
from django.db.models.functions import Coalesce
from carts.models import Cart, CartItem
from django.db.models import DecimalField, Value


class ProductMiniSerializer(serializers.Serializer):
    """
    Minimal product snapshot for cart lines (multi-vendor awareness).
    Includes producer display name.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    stock_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    unit = serializers.CharField(read_only=True)
    producer_name = serializers.SerializerMethodField()

    def get_producer_name(self, obj):
        # obj is Product
        producer = getattr(obj, "producer", None)
        if not producer:
            return None

        # Prefer business_name if it exists, otherwise fall back safely.
        if hasattr(producer, "business_name"):
            return producer.business_name
        if hasattr(producer, "name"):
            return producer.name
        return str(producer)


class CartItemSerializer(serializers.ModelSerializer):
    """
    Cart line serializer for API read responses.
    """

    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product = ProductMiniSerializer(read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product_id",
            "product",
            "quantity",
            "unit_price",
            "line_total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "product_id",
            "product",
            "unit_price",
            "line_total",
            "created_at",
            "updated_at",
        ]

    def get_line_total(self, obj: CartItem) -> Decimal:
        unit_price = obj.unit_price or Decimal("0.00")
        return unit_price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    """
    Cart serializer for API read responses.
    """

    items = CartItemSerializer(many=True, read_only=True)
    # distinct lines (from model property)
    item_count = serializers.IntegerField(read_only=True)
    total_quantity = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = [
            "id",
            "user",
            "session_key",
            "status",
            "items",
            "item_count",
            "total_quantity",
            "total_price",
            "created_at",
            "updated_at",
            "last_seen_at",
            "expires_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj):
        # distinct lines
        return obj.items.count()

    def get_total_quantity(self, obj):
        total = obj.items.aggregate(
            total=Coalesce(
                Sum("quantity"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )["total"]

        # if integral, return int for nicer UX
        if total == total.to_integral():
            return int(total)
        return str(total)


class AddToCartSerializer(serializers.Serializer):
    """
    Payload for adding an item:
    - service: cart_add_item(cart=..., product_id=..., quantity=...)
    """

    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )


class UpdateQuantitySerializer(serializers.Serializer):
    """
    Payload for setting quantity (0 removes line):
    - service: cart_set_item_quantity(cart=..., product_id=..., quantity=...)
    """

    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
