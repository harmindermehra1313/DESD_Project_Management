from rest_framework import viewsets, permissions
from products.models import (
    Category,
    Product,
    WholesalePrice,
    Allergen,
    ProductAllergen,
)
from products.api.serializers.product_details import (
    CategorySerializer,
    AllergenSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    WholesalePriceInlineSerializer,
    ProductAllergenInlineSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.all().order_by("-created_at")

    def get_queryset(self):
        qs = (
            Product.objects
            .select_related("producer", "producer__user", "category", "moderated_by_admin")
            .order_by("-created_at")
        )

        if getattr(self, "action", None) == "retrieve":
            qs = qs.prefetch_related(
                "product_wholesale",
                "product_allergen",
                "inventory_batches",
            )

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer
     

class WholesalePriceViewSet(viewsets.ModelViewSet):
    queryset = WholesalePrice.objects.all()
    serializer_class = WholesalePriceInlineSerializer


class AllergenViewSet(viewsets.ModelViewSet):
    queryset = Allergen.objects.all().order_by("name")
    serializer_class = AllergenSerializer


class ProductAllergenViewSet(viewsets.ModelViewSet):
    queryset = ProductAllergen.objects.all()
    serializer_class = ProductAllergenInlineSerializer
    