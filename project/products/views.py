# products/views.py

from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404
from .models import Product


class ProductListView(ListView):
    template_name = "products/index.html"
    context_object_name = "products"
    paginate_by = 24

    def get_queryset(self):
        return Product.objects.filter(
            status=Product.Status.PUBLISHED
        ).order_by("-created_at")


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.filter(status__in=["PUBLISHED", Product.Status.PUBLISHED])

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])