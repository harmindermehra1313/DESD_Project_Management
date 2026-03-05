from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponse # Imported for the placeholder view
from django.conf import settings
from datetime import datetime
from .models import Product, Category, Allergen, ProductAllergen
from accounts.models import Producer


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
        
    role = str(getattr(user, 'role', '')).lower()
    if role in ['producer', 'admin']:
        return True
        
    if hasattr(user, 'producer_profile'):
        return True

    return False

    
def product_list(request):
    all_products = Product.objects.filter(status=Product.Status.PUBLISHED).select_related('producer').prefetch_related('product_allergen__allergen')
    recommended_products = all_products.order_by('-created_at')[:4]
    categories = Category.objects.all()

    context = {
        'all_products': all_products,
        'recommended_products': recommended_products,
        'categories': categories, 
    }
    return render(request, 'products/products_list.html', context)

@login_required
@user_passes_test(is_producer_or_admin, login_url='/accounts/login/')
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

        new_product = Product.objects.create(
            producer=producer,
            category=category_obj, 
            name=name,
            price=price,
            availability_status=availability_status,
            harvest_date=harvest_date,
            expiry_date=expiry_date,
            unit=unit_code,
            stock_quantity=stock_quantity,
            description=description,
            image=uploaded_image,
            farm_origin="Local Farm",
            surplus_discount_percentage=0.00
        )

        if not uploaded_image:
            new_product.image.name = default_image_path
            new_product.save(update_fields=['image'])

        allergen_ids = request.POST.getlist('allergen')
        for a_code in allergen_ids:
            allergen_obj, _ = Allergen.objects.get_or_create(name=a_code)
            ProductAllergen.objects.create(
                product=new_product, 
                allergen=allergen_obj
            )

        return redirect('products_list')

    return render(request, 'products/add_product.html', _build_add_product_context())

# not linked these yet
def product_detail(request, product_id):
    # This ensures the product ID passed in the URL actually exists
    product = get_object_or_404(Product, pk=product_id)
    return HttpResponse(f"Placeholder page for: {product.name}. (Template coming soon!)")

def add_to_cart(request, product_id):
    print(f"TODO: Logic to add product {product_id} to the cart session.")
    return redirect('products_list')