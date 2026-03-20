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

    availability_label = serializers.SerializerMethodField()
    availability_badge_class = serializers.SerializerMethodField()
    stock_message = serializers.SerializerMethodField()
    is_purchasable = serializers.SerializerMethodField()
    add_to_cart_button_label = serializers.SerializerMethodField()

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
            "availability_label",
            "availability_badge_class",
            "stock_message",
            "is_purchasable",
            "add_to_cart_button_label",
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

    def _get_remaining_quantity_value(self, obj):
        active_inventory = self._get_active_inventory(obj)
        if not active_inventory:
            return 0
        return active_inventory.remaining_quantity or 0

    def _is_out_of_stock(self, obj):
        return self._get_remaining_quantity_value(obj) <= 0

    def _is_low_stock(self, obj):
        stock = self._get_remaining_quantity_value(obj)
        threshold = obj.low_stock_threshold or 0
        return stock > 0 and stock <= threshold

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
        return self._get_remaining_quantity_value(obj)

    def get_availability_label(self, obj):
        if self._is_out_of_stock(obj):
            return "Out of stock"
        if obj.availability_status == "UNAV":
            return "Unavailable"
        return "Available"

    def get_availability_badge_class(self, obj):
        if self._is_out_of_stock(obj):
            return "text-bg-danger"
        if obj.availability_status == "UNAV":
            return "text-bg-secondary"
        return "text-bg-success"

    def get_stock_message(self, obj):
        stock = self._get_remaining_quantity_value(obj)

        if stock <= 0:
            return "Out of stock"
        if self._is_low_stock(obj):
            return f"Low stock — only {stock} left"
        return "In stock"

    def get_is_purchasable(self, obj):
        return bool(self.get_active_inventory_id(obj)) and not self._is_out_of_stock(obj)

    def get_add_to_cart_button_label(self, obj):
        if self.get_is_purchasable(obj):
            return "Add to cart"
        return "Out of stock"


# Following serializers are being used by others
class ProductInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "image", "price", "unit")
class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = "__all__"
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"