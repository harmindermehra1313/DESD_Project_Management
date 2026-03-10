from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers

from carts.models import Cart, CartItem


class ProductMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="product.id", read_only=True)
    name = serializers.CharField(source="product.name", read_only=True)

    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="product.price", read_only=True
    )

    base_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="product.price", read_only=True
    )

    stock_quantity = serializers.IntegerField(
        source="remaining_quantity", read_only=True
    )

    unit = serializers.CharField(source="product.unit", read_only=True)

    producer_name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    surplus_status = serializers.CharField(read_only=True)
    surplus_discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    surplus_note = serializers.CharField(read_only=True, allow_null=True)

    def get_producer_name(self, obj):
        producer = obj.product.producer
        return getattr(producer, "business_name", None) or getattr(
            producer, "name", None
        )

    def get_image(self, obj):
        img = getattr(obj.product, "image", None)
        return getattr(img, "url", None) if img else None


#
class CartItemSerializer(serializers.ModelSerializer):
    inventory_id = serializers.IntegerField(source="inventory.id", read_only=True)
    product_id = serializers.IntegerField(source="inventory.product.id", read_only=True)
    product = ProductMiniSerializer(source="inventory", read_only=True)

    line_total = serializers.SerializerMethodField()
    base_line_total = serializers.SerializerMethodField()
    savings_total = serializers.SerializerMethodField()
    savings_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "inventory_id",
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

    def get_line_total(self, obj):
        return (obj.unit_price or 0) * (obj.quantity or 0)

    def get_base_line_total(self, obj):
        base = obj.inventory.product.price
        return Decimal(str(base)) * (obj.quantity or 0)

    def get_savings_total(self, obj):
        return self.get_base_line_total(obj) - self.get_line_total(obj)

    def get_savings_per_unit(self, obj):
        base = obj.inventory.product.price
        return Decimal(str(base)) - (obj.unit_price or 0)


class CartSerializer(serializers.ModelSerializer):
    """
    Cart serializer for API read responses.
    """

    items = CartItemSerializer(many=True, read_only=True)

    item_count = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    # keep your existing field name if your Cart model has it
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
    # product_id = serializers.IntegerField(min_value=1)
    inventory_id = serializers.IntegerField(min_value=1)
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
