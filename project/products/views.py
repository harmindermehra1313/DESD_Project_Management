from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponse # Imported for the placeholder view
from .models import Product, Category
from accounts.models import Producer

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
        unit = request.POST.get('unit')
        stock_quantity = request.POST.get('stock_quantity')
        description = request.POST.get('description')
        image = request.FILES.get('image')
        
        food_group_code = request.POST.get('category')
        
        group_names = {
            'MT': 'Meat',
            'DAE': 'Dairy and Eggs',
            'FR': 'Fruit',
            'VEG': 'Vegetables',
            'SEA': 'Seasonal'
        }
        
        category_obj, created = Category.objects.get_or_create(
            food_groups=food_group_code,
            defaults={
                'name': group_names.get(food_group_code, 'Unknown Category'),
                'vat': 0.00 # Providing a default VAT
            }
        )
        
        producer = request.user.producer_profile

        Product.objects.create(
            producer=producer,
            category=category_obj, 
            name=name,
            price=price,
            availability_status=availability_status,
            harvest_date=harvest_date,
            unit=unit,
            stock_quantity=stock_quantity,
            description=description,
            image=image,
            expiry_date=timezone.now() + timezone.timedelta(days=7),
            farm_origin="Local Farm",
            surplus_discount_percentage=0.00
        )
        return redirect('products_list')

    return render(request, 'products/add_product.html')

# not linked these yet
def product_detail(request, product_id):
    # This ensures the product ID passed in the URL actually exists
    product = get_object_or_404(Product, pk=product_id)
    return HttpResponse(f"Placeholder page for: {product.name}. (Template coming soon!)")

def add_to_cart(request, product_id):
    print(f"TODO: Logic to add product {product_id} to the cart session.")
    return redirect('products_list')