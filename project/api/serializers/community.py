from rest_framework import serializers
from community.models import Recipe, RecipeProduct, FarmStory, FavouriteRecipe
from accounts.models import Producer, User
from api.serializers.accounts import UserSerializer, ProducerSerializer
from api.serializers.products import ProductListSerializer

# Validation should happen here! TBC remove when added

class RecipeSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    moderated_by_admin = UserSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = "__all__"

class RecipeProductSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer(read_only=True)
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = RecipeProduct
        fields = "__all__"

class FarmStorySerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    moderated_by_admin = UserSerializer(read_only=True)

    class Meta:
        model = FarmStory
        fields = "__all__"

class FavouriteRecipeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    recipe = RecipeSerializer(read_only=True)

    class Meta:
        model = FavouriteRecipe
        fields = "__all__"
