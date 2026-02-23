from rest_framework import viewsets
from products.models import (
    Category,
    Product,
    WholesalePrice,
    ProductUpdateHistory,
    Allergen,
    ProductAllergen,
)
from api.serializers.products import (
    CategorySerializer,
    ProductSerializer,
    WholesalePriceSerializer,
    ProductUpdateHistorySerializer,
    AllergenSerializer,
    ProductAllergenSerializer,
)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer

class WholesalePriceViewSet(viewsets.ModelViewSet):
    queryset = WholesalePrice.objects.all()
    serializer_class = WholesalePriceSerializer

class ProductUpdateHistoryViewSet(viewsets.ModelViewSet):
    queryset = ProductUpdateHistory.objects.all().order_by("-changed_at")
    serializer_class = ProductUpdateHistorySerializer

class AllergenViewSet(viewsets.ModelViewSet):
    queryset = Allergen.objects.all().order_by("name")
    serializer_class = AllergenSerializer

class ProductAllergenViewSet(viewsets.ModelViewSet):
    queryset = ProductAllergen.objects.all()
    serializer_class = ProductAllergenSerializer