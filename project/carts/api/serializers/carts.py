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

    expiry_date = serializers.DateField(read_only=True)
    expiry_type = serializers.CharField(read_only=True)
    expiry_type_label = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_purchasable = serializers.SerializerMethodField()
    stock_message = serializers.SerializerMethodField()

    def get_producer_name(self, obj):
        producer = obj.product.producer
        return getattr(producer, "farm_name", None) or getattr(
            producer, "name", None
        )

    def get_image(self, obj):
        img = getattr(obj.product, "image", None)
        return getattr(img, "url", None) if img else None

    def get_expiry_type_label(self, obj):
        return obj.get_expiry_type_display() if obj.expiry_type else None

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_purchasable(self, obj):
        product = obj.product
        return (
            product.status == product.Status.PUBLISHED
            and product.availability_status == product.Availability_status.AVAILABLE
            and obj.remaining_quantity > 0
            and not obj.is_expired()
        )

    def get_stock_message(self, obj):
        product = obj.product

        if obj.is_expired():
            return "This product has expired. Please remove the item."

        if product.status != product.Status.PUBLISHED:
            return "This product is not available. Please remove the item."

        if product.availability_status != product.Availability_status.AVAILABLE:
            return "This product is unavailable. Please remove the item."

        if obj.remaining_quantity <= 0:
            return "This item is out of stock. Please remove the item."

        return "In stock"


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
