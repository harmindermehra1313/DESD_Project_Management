from django.views.generic import TemplateView
from django.shortcuts import render

def products_page(request):
    return render(request, "products/index.html")

class ProductDetailPage(TemplateView):
    template_name = "products/product_detail.html"