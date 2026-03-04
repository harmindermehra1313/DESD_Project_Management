from rest_framework import serializers
from products.models import (
    Category,
    Product,
    WholesalePrice,
    Allergen,
    ProductAllergen,
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
            "stock_quantity",
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
        source="product_wholesale", many=True, read_only=True
    )
    allergens = ProductAllergenInlineSerializer(
        source="product_allergen", many=True, read_only=True
    )

    class Meta:
        model = Product
        fields = "__all__" 


class ProductWriteSerializer(serializers.ModelSerializer):
    producer_id = serializers.PrimaryKeyRelatedField(
        source="producer", queryset=Producer.objects.all(), write_only=True
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
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