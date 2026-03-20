from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from datetime import datetime
from decimal import Decimal, InvalidOperation
from ..models import Product, Category, Allergen, ProductAllergen, WholesalePrice
from datetime import date, timedelta
from accounts.models import Producer
from products.models import Inventory
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Prefetch
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
        expiry_type = request.POST.get('expiry_type', Inventory.ExpiryType.BEST_BEFORE)
        organic_certification_status = request.POST.get(
            'organic_certification_status',
            Product.OrganicStatus.NOT_CERTIFIED,
        )
        unit_code = request.POST.get('unit')
        stock_quantity = request.POST.get('stock_quantity')
        wholesale_price_raw = (request.POST.get('wholesale_price') or '').strip()
        description = request.POST.get('description')
        uploaded_image = request.FILES.get('image')

        try:
            base_price_value = Decimal(str(price))
        except (TypeError, ValueError, InvalidOperation):
            return render(
                request,
                'products/add_product.html',
                _build_add_product_context('Please enter a valid base price.'),
            )

        try:
            stock_quantity_value = int(stock_quantity)
        except (TypeError, ValueError):
            return render(
                request,
                'products/add_product.html',
                _build_add_product_context('Please enter a valid stock quantity.'),
            )

        if stock_quantity_value < 0:
            return render(
                request,
                'products/add_product.html',
                _build_add_product_context('Stock quantity cannot be negative.'),
            )

        wholesale_price = None
        if wholesale_price_raw:
            try:
                wholesale_price = Decimal(wholesale_price_raw)
            except (TypeError, ValueError, InvalidOperation):
                return render(
                    request,
                    'products/add_product.html',
                    _build_add_product_context('Please enter a valid wholesale price.'),
                )

            if wholesale_price <= 0:
                return render(
                    request,
                    'products/add_product.html',
                    _build_add_product_context('Wholesale price must be greater than 0.'),
                )

            if wholesale_price > base_price_value:
                return render(
                    request,
                    'products/add_product.html',
                    _build_add_product_context('Wholesale price cannot be higher than the base price.'),
                )

            if stock_quantity_value < 20:
                return render(
                    request,
                    'products/add_product.html',
                    _build_add_product_context('At least 20 items in stock are required to set a wholesale price.'),
                )

        valid_expiry_types = {choice[0] for choice in Inventory.ExpiryType.choices}
        if expiry_type not in valid_expiry_types:
            expiry_type = Inventory.ExpiryType.BEST_BEFORE

        valid_organic_statuses = {choice[0] for choice in Product.OrganicStatus.choices}
        if organic_certification_status not in valid_organic_statuses:
            organic_certification_status = Product.OrganicStatus.NOT_CERTIFIED

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
        farm_origin = producer.farm_name.strip() if producer.farm_name else "Local Farm"

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
            price=base_price_value,
            availability_status=availability_status,
            unit=unit_code,
            organic_certification_status=organic_certification_status,
            description=description,
            image=uploaded_image,
            farm_origin=farm_origin,
        )

        if not uploaded_image:
            new_product.image.name = default_image_path
            new_product.save(update_fields=['image'])
        
        Inventory.objects.create(
            product=new_product,
            original_quantity=stock_quantity_value,
            remaining_quantity=stock_quantity_value,
            harvest_date=harvest_dt.date(),
            expiry_date=expiry_dt.date(),
            expiry_type=expiry_type,
            surplus_status="NONE",
            surplus_discount_percentage=0,
        )

        if wholesale_price is not None:
            WholesalePrice.objects.create(
                product=new_product,
                min_quantity=20,
                unit_price=wholesale_price,
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

    products = (
        Product.objects
        .filter(producer=producer)
        .select_related('category')
        .prefetch_related(
            'inventory_batches',
            'product_allergen__allergen',
            Prefetch(
                'product_wholesale',
                queryset=WholesalePrice.objects.filter(min_quantity=20).order_by('-id'),
                to_attr='product_wholesale_20',
            ),
        )
        .annotate(total_stock=Sum('inventory_batches__remaining_quantity'))
        .order_by("-created_at")
    )

    categories = Category.objects.all()

    return render(request, "products/producer_products.html", {
        "products": products,
        "categories": categories,
        "units": Product.Unit.choices,
    })


@producer_required
def edit_producer_product(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'error': 'Product name is required.'})

        try:
            price = float(data.get('price', 0))
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Invalid price value.'})

        base_price_value = Decimal(str(price))

        unit = data.get('unit', product.unit)
        valid_units = {choice[0] for choice in Product.Unit.choices}
        if unit not in valid_units:
            return JsonResponse({'success': False, 'error': 'Invalid unit.'})

        availability_status = data.get('availability_status', product.availability_status)
        valid_avail = {choice[0] for choice in Product.Availability_status.choices}
        if availability_status not in valid_avail:
            return JsonResponse({'success': False, 'error': 'Invalid availability status.'})

        organic = data.get('organic_certification_status', product.organic_certification_status)
        valid_organic = {choice[0] for choice in Product.OrganicStatus.choices}
        if organic not in valid_organic:
            return JsonResponse({'success': False, 'error': 'Invalid organic status.'})

        category_id = data.get('category_id')
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
        else:
            category = product.category

        wholesale_price_raw = str(data.get('wholesale_price', '') or '').strip()
        wholesale_price = None
        if wholesale_price_raw:
            try:
                wholesale_price = Decimal(wholesale_price_raw)
            except (TypeError, ValueError, InvalidOperation):
                return JsonResponse({'success': False, 'error': 'Please enter a valid wholesale price.'})

            if wholesale_price <= 0:
                return JsonResponse({'success': False, 'error': 'Wholesale price must be greater than 0.'})

            if wholesale_price > base_price_value:
                return JsonResponse({'success': False, 'error': 'Wholesale price cannot be higher than the base price.'})

            stock_total = product.inventory_batches.aggregate(total=Sum('remaining_quantity')).get('total') or 0
            if stock_total < 20:
                return JsonResponse({
                    'success': False,
                    'error': 'At least 20 items in stock are required to set a wholesale price.',
                })

        product.name = name
        product.price = price
        product.unit = unit
        product.availability_status = availability_status
        product.organic_certification_status = organic
        product.description = data.get('description', product.description)
        product.category = category
        product.save()

        if wholesale_price is not None:
            WholesalePrice.objects.update_or_create(
                product=product,
                min_quantity=20,
                defaults={'unit_price': wholesale_price},
            )
        else:
            product.product_wholesale.filter(min_quantity=20).delete()

        return JsonResponse({
            'success': True,
            'name': product.name,
            'price': str(product.price),
            'unit_display': product.get_unit_display(),
            'unit': product.unit,
            'category': product.category.name,
            'category_id': product.category.pk,
            'availability_status': product.availability_status,
            'availability_display': product.get_availability_status_display(),
            'organic_certification_status': product.organic_certification_status,
            'description': product.description or '',
            'wholesale_price': str(wholesale_price) if wholesale_price is not None else '',
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)


@producer_required
def cancel_producer_product(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)
    product.availability_status = Product.Availability_status.DISCONTINUED
    product.save(update_fields=['availability_status'])

    return JsonResponse({
        'success': True,
        'availability_status': product.availability_status,
        'availability_display': product.get_availability_status_display(),
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


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return (
            Product.objects.filter(status__in=["PUB", Product.Status.PUBLISHED])
            .select_related("producer", "category")
            .prefetch_related(
                "product_wholesale",
                "product_allergen__allergen",
                "inventory_batches",
            )
        )

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object

        # Expiry label (Use by vs Best before) - purely for display
        use_by_groups = {"MT", "DAE"}
        food_group = getattr(getattr(p, "category", None), "food_groups", None)
        ctx["expiry_label"] = "Use by" if food_group in use_by_groups else "Best before"

        # Wholesale tiers for JS
        tiers = list(
            p.product_wholesale.order_by("min_quantity").values("min_quantity", "unit_price")
        )
        ctx["wholesale_tiers"] = tiers

        batch = p.inventory_batches.order_by("expiry_date").first()
        ctx["stock"] = batch.remaining_quantity if batch else 0
        ctx["expiry"] = batch.expiry_date if batch else None
        ctx["batch"] = batch

        return ctx
    # return redirect('products_list')

# Harminder Edits
# def product_view(request, category_id):
#     # All categories except organic
#     categories = Category.objects.exclude(name__icontains="organic")
#     certified_organic = Category.objects.filter(name__icontains="organic")
    
#     # ALL PRODUCTS PAGE
#     if category_id == 0:
#         selected_category = None
#         products = Product.objects.filter(status="PUB")
#         show_filters = True   # show category + producer filters

#     # CATEGORY PAGE
#     else:
#         selected_category = get_object_or_404(Category, id=category_id)
#         products = Product.objects.filter(status="PUB", category=selected_category)
#         show_filters = False  # hide category + producer filters

#     # Producer list for dropdown (only used when show_filters=True)
#     producers = products.values_list("producer__farm_name", flat=True).distinct()

#     # Helper: get earliest-expiring batch
#     def get_active_batch(product):
#         return product.inventory_batches.order_by("expiry_date").first()
    
#     product_json = []
#     for p in products:
#         batch = get_active_batch(p)

#         product_json.append({
#             "id": p.id,
#             "name": p.name,
#             "description": p.description,
#             "price": float(p.price),
#             "image": p.image.url if p.image else "",
#             "producer": p.producer.farm_name,
#             "category": p.category.name,
#             "stock": batch.remaining_quantity if batch else 0,
#             "expiry": batch.expiry_date.strftime("%Y-%m-%d") if batch else "",
#         })
#     # Convert queryset → JSON for inline JS
#     # product_json = [
#     #     {
#     #         "id": p.id,
#     #         "name": p.name,
#     #         "description": p.description,
#     #         "price": float(p.price),
#     #         "image": p.image.url if p.image else "",
#     #         "producer": p.producer.farm_name,
#     #         "category": p.category.name,  # required for filtering
#     #         "stock": p.stock_quantity,
#     #         "expiry": p.expiry_date.strftime("%Y-%m-%d"),
#     #     }
#     #     for p in products
#     # ]

#     return render(request, "products/product_view.html", {
#         "categories": categories,
#         "producers": producers,
#         "products_json": json.dumps(product_json),  # safe JSON for inline JS
#         "selected_category": selected_category,
#         "show_filters": show_filters,
#         'organic': certified_organic,
#     })


def product_view(request, category_id):
    # All categories except organic
    categories = Category.objects.exclude(name__icontains="organic")
    certified_organic = Category.objects.filter(name__icontains="organic")

    # ALL PRODUCTS PAGE
    if category_id == 0:
        selected_category = None
        products = Product.objects.filter(status="PUB")
        show_filters = True

    # CATEGORY PAGE
    else:
        selected_category = get_object_or_404(Category, id=category_id)
        products = Product.objects.filter(status="PUB", category=selected_category)
        show_filters = False

    # Producer list for dropdown
    producers = products.values_list("producer__farm_name", flat=True).distinct()

    # Helper: earliest-expiring batch
    def get_active_batch(product):
        return product.inventory_batches.order_by("expiry_date").first()

    product_json = []

    for p in products:
        batch = get_active_batch(p)

        # -----------------------------
        # DISCOUNT LOGIC (Surplus)
        # -----------------------------
        original_price = float(p.price)

        if batch and batch.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE:
            discount_percent = float(batch.surplus_discount_percentage)
            discounted_price = float(original_price * (100 - discount_percent) / 100)
            has_discount = True
        else:
            discounted_price = original_price
            discount_percent = 0
            has_discount = False

        # -----------------------------
        # BADGES
        # -----------------------------

        # Organic badge
        organic = (p.organic_certification_status == Product.OrganicStatus.CERTIFIED)

        # Local badge (farm origin matches producer name)
        local = (p.farm_origin.lower() == p.producer.farm_name.lower())

        # Fresh Today badge (48-hour freshness window)
        if batch:
            days_old = (date.today() - batch.harvest_date).days
            fresh_today = days_old <= 1
        else:
            fresh_today = False

        # Low stock badge
        low_stock = (batch.remaining_quantity <= p.low_stock_threshold) if batch else False

        # -----------------------------
        # BUILD JSON ENTRY
        # -----------------------------
        product_json.append({
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "price": discounted_price,
            "original_price": original_price,
            "has_discount": has_discount,
            "discount_percent": discount_percent,

            "organic": organic,
            "local": local,
            "fresh_today": fresh_today,
            "low_stock": low_stock,

            "image": p.image.url if p.image else "",
            "producer": p.producer.farm_name,
            "category": p.category.name,

            "stock": batch.remaining_quantity if batch else 0,
            "expiry": batch.expiry_date.strftime("%Y-%m-%d") if batch else "",
        })

    return render(request, "products/product_view.html", {
        "categories": categories,
        "producers": producers,
        "products_json": json.dumps(product_json),
        "selected_category": selected_category,
        "show_filters": show_filters,
        "organic": certified_organic,
    })

# Pippal
def product_detail_page(request, product_id):
    return render(request, "products/product_detail.html", {"product_id": product_id})