from products.models import Category
from products.models import Product
from accounts.models import Producer

def product_categories(request):
    categories = Category.objects.exclude(name__icontains="organic")
    certified_organic = Category.objects.filter(name__icontains="organic")
    return {"header_categories": categories,
            'organic': certified_organic,}


def admin_pending_requests(request):

    pending_products = Product.objects.filter(
        status=Product.Status.PENDING
    ).count()

    pending_producers = Producer.objects.filter(
        is_approved=False
    ).count()

    return {
        "pending_count": pending_products + pending_producers
    }