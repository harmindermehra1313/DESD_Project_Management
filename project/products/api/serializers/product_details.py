from decimal import Decimal

from rest_framework import serializers
from products.models import (
    Category,
    Product,
    WholesalePrice,
    Allergen,
    ProductAllergen,
    Inventory,
)
from accounts.models import Producer
from api.serializers.accounts import ProducerSerializer, AdminSerializer


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class WholesalePriceInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = WholesalePrice
        exclude = ("product",)


class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = "__all__"


class ProductAllergenInlineSerializer(serializers.ModelSerializer):
    allergen = AllergenSerializer(read_only=True)

    class Meta:
        model = ProductAllergen
        fields = ("id", "allergen")


class ProductListSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "description",
            "price",
            "unit",
            "image",
            "availability_status",
            "status",
            "producer",
            "category",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    moderated_by_admin = AdminSerializer(read_only=True)

    wholesale_prices = WholesalePriceInlineSerializer(
        source="product_wholesale",
        many=True,
        read_only=True,
    )
    allergens = ProductAllergenInlineSerializer(
        source="product_allergen",
        many=True,
        read_only=True,
    )

    effective_price = serializers.SerializerMethodField()
    active_inventory_id = serializers.SerializerMethodField()
    surplus_active = serializers.SerializerMethodField()
    surplus_discount_percentage = serializers.SerializerMethodField()
    remaining_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "producer",
            "category",
            "moderated_by_admin",
            "name",
            "description",
            "price",
            "effective_price",
            "active_inventory_id",
            "surplus_active",
            "surplus_discount_percentage",
            "remaining_quantity",
            "unit",
            "image",
            "low_stock_threshold",
            "farm_origin",
            "organic_certification_status",
            "storage_guidance",
            "availability_start",
            "availability_end",
            "availability_status",
            "created_at",
            "updated_at",
            "status",
            "moderated_at",
            "wholesale_prices",
            "allergens",
        )

    def _get_active_inventory(self, obj):
        return (
            obj.inventory_batches
            .filter(remaining_quantity__gt=0)
            .order_by("expiry_date", "created_at")
            .first()
        )

    def get_effective_price(self, obj):
        active_inventory = self._get_active_inventory(obj)
        if not active_inventory:
            return obj.price

        base_price = obj.price
        if (
            active_inventory.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE
            and active_inventory.surplus_discount_percentage is not None
        ):
            discount_factor = (
                Decimal("100") - active_inventory.surplus_discount_percentage
            ) / Decimal("100")
            return (base_price * discount_factor).quantize(Decimal("0.01"))

        return base_price

    def get_active_inventory_id(self, obj):
        active_inventory = self._get_active_inventory(obj)
        return active_inventory.id if active_inventory else None

    def get_surplus_active(self, obj):
        active_inventory = self._get_active_inventory(obj)
        return bool(
            active_inventory
            and active_inventory.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE
        )

    def get_surplus_discount_percentage(self, obj):
        active_inventory = self._get_active_inventory(obj)
        if not active_inventory:
            return None
        return active_inventory.surplus_discount_percentage

    def get_remaining_quantity(self, obj):
        active_inventory = self._get_active_inventory(obj)
        if not active_inventory:
            return 0
        return active_inventory.remaining_quantity


class ProductWriteSerializer(serializers.ModelSerializer):
    producer_id = serializers.PrimaryKeyRelatedField(
        source="producer",
        queryset=Producer.objects.all(),
        write_only=True,
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Product
        fields = "__all__"


class ProductInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "price",
            "unit",
            "image",
            "availability_status",
            "status",
        )
        read_only_fields = fields


class InventorySerializer(serializers.ModelSerializer):
    product = ProductInlineSerializer(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "product",
            "remaining_quantity",
            "harvest_date",
            "expiry_date",
            "expiry_type",
            "surplus_status",
            "surplus_discount_percentage",
            "surplus_expiry",
            "surplus_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields