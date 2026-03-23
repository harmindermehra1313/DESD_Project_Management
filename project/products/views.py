from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponse # Imported for the placeholder view
from django.conf import settings
from datetime import datetime
from .models import Product, Category, Allergen, ProductAllergen
from accounts.models import Producer
from products.models import Inventory
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from BRFN.decorators import admin_required, producer_required
import json


def _get_category_default_image(category_obj):
    image_map = getattr(settings, 'DEFAULT_PRODUCT_IMAGES_BY_GROUP', {})
    fallback = getattr(settings, 'DEFAULT_PRODUCT_IMAGE', 'products/img/default-product.png')

    # Primary match: Category.food_groups code
    food_group = str(getattr(category_obj, 'food_groups', '') or '').strip().upper()
    if food_group in image_map:
        return image_map[food_group]

    aliases = {
        'MEAT': 'MT',
        'FRUIT': 'FR',
        'VEGETABLE': 'VEG',
        'VEGETABLES': 'VEG',
        'DAIRY': 'DAE',
        'EGGS': 'DAE',
        'DAIRY_AND_EGGS': 'DAE',
        'SEASONAL': 'SEA',
    }
    alias_code = aliases.get(food_group)
    if alias_code and alias_code in image_map:
        return image_map[alias_code]

    # Final fallback based on category name text
    category_name = str(getattr(category_obj, 'name', '') or '').lower()
    if 'meat' in category_name and 'MT' in image_map:
        return image_map['MT']
    if 'fruit' in category_name and 'FR' in image_map:
        return image_map['FR']
    if ('vegetable' in category_name or 'veg' in category_name) and 'VEG' in image_map:
        return image_map['VEG']
    if ('dairy' in category_name or 'egg' in category_name) and 'DAE' in image_map:
        return image_map['DAE']
    if 'season' in category_name and 'SEA' in image_map:
        return image_map['SEA']

    return fallback


def _build_add_product_context(error_message=None):
    categories = Category.objects.all()
    units = Product.Unit.choices
    allergens = [
        {'value': value, 'label': label}
        for value, label in Allergen.Allergens.choices
        if value != Allergen.Allergens.NONE
    ]

    context = {
        'categories': categories,
        'units': units,
        'allergens': allergens,
    }

    if error_message:
        context['error_message'] = error_message

    return context

def is_producer_or_admin(user):
    if not user.is_authenticated:
        return False

    role = str(getattr(user, "role", "")).lower()
    if role in ["producer", "admin"]:
        return True

    if hasattr(user, "producer_profile"):
        return True

    return False


# def product_list(request):
#     all_products = (
#         Product.objects.filter(status=Product.Status.PUBLISHED)
#         .select_related("producer")
#         .prefetch_related("product_allergen__allergen")
#     )
#     recommended_products = all_products.order_by("-created_at")[:4]
#     categories = Category.objects.all()

#     context = {
#         "all_products": all_products,
#         "recommended_products": recommended_products,
#         "categories": categories,
#     }
#     return render(request, "products/products_list.html", context)


@producer_required
@user_passes_test(is_producer_or_admin, login_url="/accounts/login/")
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        availability_status = request.POST.get('availability_status')
        harvest_date = request.POST.get('harvest_date')
        expiry_date = request.POST.get('expiry_date')
        unit_code = request.POST.get('unit')
        stock_quantity = request.POST.get('stock_quantity')
        description = request.POST.get('description')
        uploaded_image = request.FILES.get('image')

        try:
            harvest_dt = datetime.strptime(harvest_date, '%Y-%m-%dT%H:%M')
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%dT%H:%M')
        except (TypeError, ValueError):
            return render(
                request,
                'products/add_product.html',
                _build_add_product_context('Please enter valid harvest and expiry dates.'),
            )

        if harvest_dt > expiry_dt:
            return render(
                request,
                'products/add_product.html',
                _build_add_product_context('Harvest date cannot be after expiry date.'),
            )
        

        #expiry_date=expiry_date

        category_id = request.POST.get('category')
        
        category_obj = get_object_or_404(Category, id=category_id)
        default_image_path = _get_category_default_image(category_obj)
        
        producer = request.user.producer_profile

        # new_product = Product.objects.create(
        #     producer=producer,
        #     category=category_obj,
        #     name=name,
        #     price=price,
        #     availability_status=availability_status,
        #     harvest_date=harvest_date,
        #     expiry_date=expiry_date,
        #     unit=unit_code,
        #     stock_quantity=stock_quantity,
        #     description=description,
        #     image=uploaded_image,
        #     farm_origin="Local Farm",
        #     surplus_discount_percentage=0.00,
        # )

        new_product = Product.objects.create(
            producer=producer,
            category=category_obj,
            name=name,
            price=price,
            availability_status=availability_status,
            unit=unit_code,
            description=description,
            image=uploaded_image,
            farm_origin="Local Farm",
        )

        if not uploaded_image:
            new_product.image.name = default_image_path
            new_product.save(update_fields=['image'])
        
        Inventory.objects.create(
            product=new_product,
            original_quantity=stock_quantity,
            remaining_quantity=stock_quantity,
            harvest_date=harvest_dt.date(),
            expiry_date=expiry_dt.date(),
            expiry_type="BB",
            surplus_status="NONE",
            surplus_discount_percentage=0,
        )

        allergen_ids = request.POST.getlist('allergen')
        for a_code in allergen_ids:
            allergen_obj, _ = Allergen.objects.get_or_create(name=a_code)
            ProductAllergen.objects.create(
                product=new_product, 
                allergen=allergen_obj
            )

        return redirect('product_view', category_id=0)

    return render(request, 'products/add_product.html', _build_add_product_context())



@producer_required
def producer_products(request):
    producer = request.user.producer_profile

    products = Product.objects.filter(producer=producer).order_by("-created_at")

    return render(request, "products/producer_products.html", {
        "products": products
    })


def add_to_cart(request, product_id):
    print(f"TODO: Logic to add product {product_id} to the cart session.")
    return redirect('product_view', category_id=0)


# products/views.py


# class ProductListView(ListView):
#     template_name = "products/index.html"
#     context_object_name = "products"
#     paginate_by = 24

#     def get_queryset(self):
#         return Product.objects.filter(status=Product.Status.PUBLISHED).order_by(
#             "-created_at"
#         )

# Oishik Edits
def product_detail_page(request, product_id):
    return render(request, "products/product_detail.html", {"product_id": product_id})

# Harminder Edits
def product_view(request, category_id):
    # All categories except organic
    categories = Category.objects.exclude(name__icontains="organic")
    certified_organic = Category.objects.filter(name__icontains="organic")
    
    # ALL PRODUCTS PAGE
    if category_id == 0:
        selected_category = None
        products = Product.objects.filter(status="PUB")
        show_filters = True   # show category + producer filters

    # CATEGORY PAGE
    else:
        selected_category = get_object_or_404(Category, id=category_id)
        products = Product.objects.filter(status="PUB", category=selected_category)
        show_filters = False  # hide category + producer filters

    # Producer list for dropdown (only used when show_filters=True)
    producers = products.values_list("producer__farm_name", flat=True).distinct()

    # Helper: get earliest-expiring batch
    def get_active_batch(product):
        return product.inventory_batches.order_by("expiry_date").first()
    
    product_json = []
    for p in products:
        batch = get_active_batch(p)

        product_json.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": float(p.price),
            "image": p.image.url if p.image else "",
            "producer": p.producer.farm_name,
            "category": p.category.name,
            "stock": batch.remaining_quantity if batch else 0,
            "expiry": batch.expiry_date.strftime("%Y-%m-%d") if batch else "",
        })
    # Convert queryset → JSON for inline JS
    # product_json = [
    #     {
    #         "id": p.id,
    #         "name": p.name,
    #         "description": p.description,
    #         "price": float(p.price),
    #         "image": p.image.url if p.image else "",
    #         "producer": p.producer.farm_name,
    #         "category": p.category.name,  # required for filtering
    #         "stock": p.stock_quantity,
    #         "expiry": p.expiry_date.strftime("%Y-%m-%d"),
    #     }
    #     for p in products
    # ]

    return render(request, "products/product_view.html", {
        "categories": categories,
        "producers": producers,
        "products_json": json.dumps(product_json),  # safe JSON for inline JS
        "selected_category": selected_category,
        "show_filters": show_filters,
        'organic': certified_organic,
    })
