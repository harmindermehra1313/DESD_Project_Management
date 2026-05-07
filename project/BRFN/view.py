from django.shortcuts import render

def custom_400(request, exception=None):
    return render(request, "errors/400.html", status=400)

def custom_403(request, exception=None):
    return render(request, "errors/403.html", status=403)

def custom_404(request, exception=None):
    return render(request, "errors/404.html", status=404)

def custom_500(request):
    return render(request, "errors/500.html", status=500)

from django.shortcuts import render
from django.db.models import Q

from products.models import Product
from community.models import Recipe, FarmStory
from accounts.models import Producer, User
from orders.models import Order


def global_search(request):
    query = request.GET.get("q", "").strip()

    products = Product.objects.none()
    recipes = Recipe.objects.none()
    stories = FarmStory.objects.none()
    producers = Producer.objects.none()
    users = User.objects.none()
    orders = Order.objects.none()

    role = getattr(request.user, "role", "GUEST") if request.user.is_authenticated else "GUEST"

    if query:
        # ADMIN: can search admin data
        if request.user.is_authenticated and role == "ADMIN":
            products = Product.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(producer__farm_name__icontains=query)
            ).select_related("producer", "category").distinct()[:20]

            producers = Producer.objects.filter(
                Q(farm_name__icontains=query) |
                Q(contact_email__icontains=query) |
                Q(contact_phone__icontains=query) |
                Q(user__name__icontains=query)
            ).select_related("user").distinct()[:20]

            users = User.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query)
            ).distinct()[:20]

            orders = Order.objects.filter(
                Q(unique_reference__icontains=query) |
                Q(user__name__icontains=query)
            ).select_related("user").distinct()[:20]

        # PRODUCER: only own content
        elif request.user.is_authenticated and role == "PRODUCER":
            producer = request.user.producer_profile

            products = Product.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query),
                producer=producer
            ).select_related("producer", "category").distinct()[:20]

            recipes = Recipe.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query),
                producer=producer
            ).select_related("producer").distinct()[:20]

            stories = FarmStory.objects.filter(
                Q(title__icontains=query) |
                Q(body__icontains=query),
                producer=producer
            ).select_related("producer").distinct()[:20]

        # CUSTOMER / GUEST: public published content only
        else:
            products = Product.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(product_type__name__icontains=query) |
                Q(producer__farm_name__icontains=query),
                status=Product.Status.PUBLISHED,
                producer__is_approved=True,
                producer__user__is_active=True,
            ).select_related("producer", "category", "product_type").distinct()[:20]

            recipes = Recipe.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(producer__farm_name__icontains=query),
                status=Recipe.Status_choices.PUBLISHED,
                producer__is_approved=True,
                producer__user__is_active=True,
            ).select_related("producer").distinct()[:20]

            stories = FarmStory.objects.filter(
                Q(title__icontains=query) |
                Q(body__icontains=query) |
                Q(producer__farm_name__icontains=query),
                status=FarmStory.Status_choices.PUBLISHED,
                producer__is_approved=True,
                producer__user__is_active=True,
            ).select_related("producer").distinct()[:20]

    return render(request, "result.html", {
        "query": query,
        "role": role,
        "products": products,
        "recipes": recipes,
        "stories": stories,
        "producers": producers,
        "users": users,
        "orders": orders,
    })