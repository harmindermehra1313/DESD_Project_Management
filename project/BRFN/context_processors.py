from products.models import Category

def product_categories(request):
    categories = Category.objects.exclude(name__icontains="organic")
    return {"header_categories": categories}