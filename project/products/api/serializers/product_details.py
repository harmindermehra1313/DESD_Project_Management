# added food miles - joe
from decimal import Decimal
from django.utils import timezone

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
from community.models import FarmStory, Recipe
from orders.services.food_miles import calculate_food_miles, get_default_delivery_postcode


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

    wholesale_prices = serializers.SerializerMethodField()
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

    expiry_date = serializers.SerializerMethodField()
    expiry_type = serializers.SerializerMethodField()
    expiry_type_label = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    availability_label = serializers.SerializerMethodField()
    availability_badge_class = serializers.SerializerMethodField()
    stock_message = serializers.SerializerMethodField()
    is_purchasable = serializers.SerializerMethodField()
    add_to_cart_button_label = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    # stories = serializers.SerializerMethodField()
    customer_postcode = serializers.SerializerMethodField()
    food_miles = serializers.SerializerMethodField()
    food_miles_login_required = serializers.SerializerMethodField()

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
            "expiry_date",
            "expiry_type",
            "expiry_type_label",
            "is_expired",
            "availability_label",
            "availability_badge_class",
            "stock_message",
            "is_purchasable",
            "add_to_cart_button_label",
            "unit",
            "image",
            "low_stock_threshold",
            "farm_origin",
            "customer_postcode",
            "food_miles",
            "food_miles_login_required",
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
            "recipes",
        )

    def _get_active_batches(self, obj):
        return obj.inventory_batches.filter(
            status=Inventory.BatchStatus.ACTIVE
        )

    def _all_batches_deleted(self, obj):
        all_batches = obj.inventory_batches.all()
        return all_batches.exists() and not all_batches.filter(
            status=Inventory.BatchStatus.ACTIVE
        ).exists()

    def _get_active_inventory(self, obj):
        today = timezone.localdate()
        return (
            self._get_active_batches(obj)
            .filter(
                remaining_quantity__gt=0,
                expiry_date__gte=today,
            )
            .order_by("expiry_date", "created_at")
            .first()
        )

    def _get_next_inventory_batch(self, obj):
        """
        Earliest non-deleted stock batch regardless of expiry.
        Useful for determining whether remaining stock exists
        but is already expired.
        """
        return (
            self._get_active_batches(obj)
            .filter(remaining_quantity__gt=0)
            .order_by("expiry_date", "created_at")
            .first()
        )
    def get_recipes(self, obj):
        from community.models import Recipe

        qs = Recipe.objects.filter(
            recipe_products__product=obj,
            status=Recipe.Status_choices.PUBLISHED
        ).order_by("-created_at")

        return RecipeInlineSerializer(qs, many=True).data



    # def get_stories(self, obj):
    #     from community.models import FarmStory

    #     qs = FarmStory.objects.filter(
    #         producer=obj.producer,
    #         status=FarmStory.Status.PUBLISHED
    #     ).order_by("-created_at")

    #     return StoryInlineSerializer(qs, many=True).data


    def _has_only_expired_stock(self, obj):
        next_batch = self._get_next_inventory_batch(obj)
        if not next_batch:
            return False
        return next_batch.is_expired() and self._get_active_inventory(obj) is None

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
        return threshold > 0 and stock > 0 and stock <= threshold

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

    def _get_inventory_for_display(self, obj):
        active_inventory = self._get_active_inventory(obj)
        if active_inventory:
            return active_inventory
        return self._get_next_inventory_batch(obj)

    def get_expiry_date(self, obj):
        inventory = self._get_inventory_for_display(obj)
        return inventory.expiry_date if inventory else None

    def get_expiry_type(self, obj):
        inventory = self._get_inventory_for_display(obj)
        return inventory.expiry_type if inventory else None

    def get_expiry_type_label(self, obj):
        inventory = self._get_inventory_for_display(obj)
        return inventory.get_expiry_type_display() if inventory else None

    def get_is_expired(self, obj):
        return self._has_only_expired_stock(obj)

    def _is_wholesale_customer(self):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        customer = getattr(request.user, "customer_profile", None)
        if not customer:
            return False

        return customer.organisation_type in {"BUSINESS", "COMMUNITY_GROUP"}

    def get_wholesale_prices(self, obj):
        if not self._is_wholesale_customer():
            return []

        return WholesalePriceInlineSerializer(
            obj.product_wholesale.all(),
            many=True,
            context=self.context,
        ).data

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
        if self._all_batches_deleted(obj):
            return "Unavailable"

        if self.get_is_expired(obj):
            return "Expired"

        if obj.availability_status == Product.Availability_status.DISCONTINUED:
            return "Discontinued"

        if obj.availability_status != Product.Availability_status.AVAILABLE:
            return "Unavailable"

        if self._is_out_of_stock(obj):
            return "Out of stock"

        if self._is_low_stock(obj):
            return "Low stock"

        return "Available"

    def get_availability_badge_class(self, obj):
        if self._all_batches_deleted(obj):
            return "text-bg-secondary"

        if self.get_is_expired(obj):
            return "text-bg-danger"

        if obj.availability_status == Product.Availability_status.DISCONTINUED:
            return "text-bg-secondary"

        if obj.availability_status != Product.Availability_status.AVAILABLE:
            return "text-bg-secondary"

        if self._is_out_of_stock(obj):
            return "text-bg-danger"

        if self._is_low_stock(obj):
            return "bg-warning text-dark"

        return "text-bg-success"

    def get_stock_message(self, obj):
        if self._all_batches_deleted(obj):
            return "Product no longer available"

        if self.get_is_expired(obj):
            return "Expired"

        if obj.availability_status == Product.Availability_status.DISCONTINUED:
            return "Discontinued"

        if obj.availability_status != Product.Availability_status.AVAILABLE:
            return "Unavailable"

        stock = self._get_remaining_quantity_value(obj)
    
        if stock <= 0:
            return "Out of stock"

        if self._is_low_stock(obj):
            return f"Only {stock} left"

        return f"{stock} remaining"

    def get_is_purchasable(self, obj):
        return (
            obj.status == Product.Status.PUBLISHED
            and obj.availability_status == Product.Availability_status.AVAILABLE
            and not self._all_batches_deleted(obj)
            and bool(self.get_active_inventory_id(obj))
            and not self._is_out_of_stock(obj)
            and not self.get_is_expired(obj)
        )

    def get_add_to_cart_button_label(self, obj):
        if self._all_batches_deleted(obj):
            return "No longer available"
        if self.get_is_expired(obj):
            return "Expired"
        if self.get_is_purchasable(obj):
            return "Add to cart"
        return "Unavailable"

    def get_customer_postcode(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        return get_default_delivery_postcode(request.user)

    def get_food_miles(self, obj):
        customer_postcode = self.get_customer_postcode(obj)
        return calculate_food_miles(obj.producer.farm_postcode, customer_postcode)

    def get_food_miles_login_required(self, obj):
        request = self.context.get("request")
        return bool(request and not request.user.is_authenticated)


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

class RecipeInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "title", "image", "seasonal_tag", "created_at")
# class StoryInlineSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = FarmStory
#         fields = ("id", "title", "image", "created_at")
