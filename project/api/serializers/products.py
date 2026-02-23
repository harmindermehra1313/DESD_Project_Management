from rest_framework import serializers
from products.models import (
    Category,
    Product,
    WholesalePrice,
    ProductUpdateHistory,
    Allergen,
    ProductAllergen,
)
from api.serializers.accounts import ProducerSerializer, AdminSerializer, UserSerializer

# Validation should happen here! TBC remove when added

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"

class ProductSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    moderated_by_admin = AdminSerializer(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"

class WholesalePriceSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = WholesalePrice
        fields = "__all__"

class ProductUpdateHistorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = ProductUpdateHistory
        fields = "__all__"

class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = "__all__"

class ProductAllergenSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    allergen = AllergenSerializer(read_only=True)

    class Meta:
        model = ProductAllergen
        fields = "__all__"