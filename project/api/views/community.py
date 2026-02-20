from rest_framework import viewsets
from community.models import Recipe, RecipeProduct, FarmStory, FavouriteRecipe
from api.serializers.community import (
    RecipeSerializer,
    RecipeProductSerializer,
    FarmStorySerializer,
    FavouriteRecipeSerializer,
)

class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by("-created_at")
    serializer_class = RecipeSerializer

class RecipeProductViewSet(viewsets.ModelViewSet):
    queryset = RecipeProduct.objects.all()
    serializer_class = RecipeProductSerializer

class FarmStoryViewSet(viewsets.ModelViewSet):
    queryset = FarmStory.objects.all().order_by("-created_at")
    serializer_class = FarmStorySerializer

class FavouriteRecipeViewSet(viewsets.ModelViewSet):
    queryset = FavouriteRecipe.objects.all().order_by("-created_at")
    serializer_class = FavouriteRecipeSerializer