from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers

from carts.models import Cart, CartItem


class ProductMiniSerializer(serializers.Serializer):
    """
    Minimal product snapshot for cart lines (multi-vendor awareness).
    Includes producer display name + base_unit_price for wholesale UI.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)

    # This is the product's normal price (non-wholesale baseline)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    # IMPORTANT: Frontend expects this name
    base_unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        source="price",
        read_only=True,
    )

    # Keep as int-like in payload (your Product model uses IntegerField)
    stock_quantity = serializers.IntegerField(read_only=True)

    unit = serializers.CharField(read_only=True)

    producer_name = serializers.SerializerMethodField()

    # Optional: include image if you want thumbnails
    image = serializers.SerializerMethodField()
    
    surplus_status = serializers.CharField(read_only=True)
    surplus_discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )
    surplus_note = serializers.CharField(read_only=True, allow_null=True)

    def get_producer_name(self, obj):
        producer = getattr(obj, "producer", None)
        if not producer:
            return None
        if hasattr(producer, "business_name") and producer.business_name:
            return producer.business_name
        if hasattr(producer, "name") and producer.name:
            return producer.name
        return str(producer)

    def get_image(self, obj):
        img = getattr(obj, "image", None)
        if not img:
            return None
        url = getattr(img, "url", None)
        return url or None


class CartItemSerializer(serializers.ModelSerializer):
    """
    Cart line serializer for API read responses.
    """

    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product = ProductMiniSerializer(read_only=True)

    line_total = serializers.SerializerMethodField()

    # Optional (but nice for UI): expose baseline + savings
    base_line_total = serializers.SerializerMethodField()
    savings_total = serializers.SerializerMethodField()
    savings_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product_id",
            "product",
            "quantity",
            "unit_price",
            "line_total",
            "base_line_total",
            "savings_total",
            "savings_per_unit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_line_total(self, obj: CartItem) -> Decimal:
        unit_price = obj.unit_price or Decimal("0.00")
        qty = obj.quantity or Decimal("0.00")
        return unit_price * qty

    def get_base_line_total(self, obj: CartItem) -> Decimal:
        base = getattr(obj.product, "price", None) or Decimal("0.00")
        qty = obj.quantity or Decimal("0.00")
        return Decimal(str(base)) * qty

    def get_savings_total(self, obj: CartItem) -> Decimal:
        base_total = self.get_base_line_total(obj)
        line_total = self.get_line_total(obj)
        return base_total - line_total

    def get_savings_per_unit(self, obj: CartItem) -> Decimal:
        base = getattr(obj.product, "price", None) or Decimal("0.00")
        unit = obj.unit_price or Decimal("0.00")
        return Decimal(str(base)) - unit


class CartSerializer(serializers.ModelSerializer):
    """
    Cart serializer for API read responses.
    """

    items = CartItemSerializer(many=True, read_only=True)

    item_count = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    # keep your existing field name if your Cart model has it
    total_price = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

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

        if total == total.to_integral():
            return int(total)
        return str(total)


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )


class UpdateQuantitySerializer(serializers.Serializer):
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )