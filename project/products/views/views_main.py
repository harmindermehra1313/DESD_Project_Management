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
from django.db.models import Q, Sum, Prefetch, Case, When, Value, IntegerField
from BRFN.decorators import admin_required, producer_required
import json
from notifications.services.notifications import NotificationService
from notifications.models import Notification
from admin_records.models import ModerationLog
from products.serializers import ProductCreateSerializer


from rest_framework.decorators import api_view
from rest_framework.response import Response
from community.models import Recipe
from django.core.paginator import Paginator
from products.services.product_type_inference import get_or_create_inferred_product_type


@api_view(["GET"])
def product_recipes(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"recipes": []})

    qs = Recipe.objects.filter(
        linked_products=product, status=Recipe.Status.PUBLISHED
    ).order_by("-created_at")

    data = [
        {
            "id": r.id,
            "title": r.title,
            "image": r.image.url if r.image else "",
            "season": r.season,
        }
        for r in qs
    ]

    return Response({"recipes": data})


def _get_category_default_image(category_obj):
    image_map = getattr(settings, "DEFAULT_PRODUCT_IMAGES_BY_GROUP", {})
    fallback = getattr(
        settings, "DEFAULT_PRODUCT_IMAGE", "products/img/default-product.png"
    )

    # Primary match: Category.food_groups code
    food_group = str(getattr(category_obj, "food_groups", "") or "").strip().upper()
    if food_group in image_map:
        return image_map[food_group]

    aliases = {
        "MEAT": "MT",
        "FRUIT": "FR",
        "VEGETABLE": "VEG",
        "VEGETABLES": "VEG",
        "DAIRY": "DAE",
        "EGGS": "DAE",
        "DAIRY_AND_EGGS": "DAE",
        "SEASONAL": "SEA",
    }
    alias_code = aliases.get(food_group)
    if alias_code and alias_code in image_map:
        return image_map[alias_code]

    # Final fallback based on category name text
    category_name = str(getattr(category_obj, "name", "") or "").lower()
    if "meat" in category_name and "MT" in image_map:
        return image_map["MT"]
    if "fruit" in category_name and "FR" in image_map:
        return image_map["FR"]
    if ("vegetable" in category_name or "veg" in category_name) and "VEG" in image_map:
        return image_map["VEG"]
    if ("dairy" in category_name or "egg" in category_name) and "DAE" in image_map:
        return image_map["DAE"]
    if "season" in category_name and "SEA" in image_map:
        return image_map["SEA"]

    return fallback


def _build_add_product_context(error_message=None):
    categories = Category.objects.all()
    units = Product.Unit.choices
    allergens = [
        {"value": value, "label": label}
        for value, label in Allergen.Allergens.choices
        if value != Allergen.Allergens.NONE
    ]

    context = {
        "categories": categories,
        "units": units,
        "allergens": allergens,
    }

    if error_message:
        context["error_message"] = error_message

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


@producer_required
@user_passes_test(is_producer_or_admin, login_url="/accounts/login/")
def add_product(request):
    if request.method == "POST":
        # Combine POST data and FILES for the serializer
        data = request.POST.copy()

        # Format arrays for the serializer
        data.setlist('allergen', request.POST.getlist('allergen'))

        # Handle empty optional number fields before serialization
        if not data.get('wholesale_price'): data['wholesale_price'] = None
        if not data.get('wholesale_min_quantity'): data['wholesale_min_quantity'] = None

        serializer = ProductCreateSerializer(data=data)

        # Combine with file uploads
        if request.FILES:
            serializer.initial_data['image'] = request.FILES.get('image')

        if not serializer.is_valid():
            # Extract first error message for the UI
            error_msg = next(iter(serializer.errors.values()))[0]
            return render(request, "products/add_product.html", _build_add_product_context(error_msg))

        validated_data = serializer.validated_data

        # Process Category (Single category)
        category_id = validated_data['category']
        category_obj = get_object_or_404(Category, id=category_id)

        product_type = get_or_create_inferred_product_type(
            name=validated_data['name'],
            category=category_obj,
        )
        default_image_path = _get_category_default_image(category_obj)

        producer = request.user.producer_profile
        farm_origin = producer.farm_name.strip() if producer.farm_name else "Local Farm"

        new_product = Product.objects.create(
            producer=producer,
            category=category_obj,
            product_type=product_type,
            name=validated_data['name'],
            price=validated_data['price'],
            availability_status=validated_data['availability_status'],
            unit=validated_data['unit'],
            organic_certification_status=validated_data['organic_certification_status'],
            description=validated_data['description'],
            image=validated_data.get('image'),
            low_stock_threshold=validated_data.get('low_stock_threshold', 0),
            storage_guidance=validated_data.get('storage_guidance', ''),
            farm_origin=farm_origin,
            status=Product.Status.PENDING,
        )

        if not validated_data.get('image'):
            new_product.image.name = default_image_path
            new_product.save(update_fields=["image"])

        Inventory.objects.create(
            product=new_product,
            original_quantity=validated_data['stock_quantity'],
            remaining_quantity=validated_data['stock_quantity'],
            harvest_date=validated_data['harvest_date'],
            expiry_date=validated_data['expiry_date'],
            expiry_type=validated_data['expiry_type'],
            surplus_status="NONE",
            surplus_discount_percentage=0,
        )

        if validated_data.get('wholesale_price'):
            WholesalePrice.objects.create(
                product=new_product,
                min_quantity=validated_data['wholesale_min_quantity'],
                unit_price=validated_data['wholesale_price'],
            )

        for a_code in validated_data.get('allergen', []):
            allergen_obj, _ = Allergen.objects.get_or_create(name=a_code)
            ProductAllergen.objects.create(product=new_product, allergen=allergen_obj)

        return redirect("products:producer_products")

    return render(request, "products/add_product.html", _build_add_product_context())


@producer_required
def producer_products(request):
    producer = request.user.producer_profile

    products = (
        Product.objects.filter(producer=producer)
        .select_related("category", "product_type")
        .prefetch_related(
            Prefetch(
                "inventory_batches",
                queryset=Inventory.objects.filter(status="ACT").order_by("expiry_date"),
                to_attr="active_batches",
            ),
            Prefetch(
                "inventory_batches",
                queryset=Inventory.objects.filter(status="DEL").order_by("expiry_date"),
                to_attr="deleted_batches",
            ),
            Prefetch(
                "inventory_batches",
                queryset=Inventory.objects.filter(
                    status="ACT", expiry_date__lt=date.today()
                ).order_by("expiry_date"),
                to_attr="expired_batches",
            ),
            "product_allergen__allergen",
            Prefetch(
                "product_wholesale",
                queryset=WholesalePrice.objects.order_by("-id"),
                to_attr="product_wholesale_first",
            ),
        )
        .annotate(
            total_stock=Sum(
                "inventory_batches__remaining_quantity",
                filter=Q(inventory_batches__status="ACT"),
            )
        )
        .order_by("-created_at")
    )

    # Attach latest rejection log manually
    for p in products:
        p.latest_rejection = (
            ModerationLog.objects.filter(
                content=p.id,
                content_type=ModerationLog.ContentType.PRODUCT,
                action=ModerationLog.Action.REJECTED,
            )
            .order_by("-created_at")
            .first()
        )

    categories = Category.objects.all()

    return render(
        request,
        "products/producer_products.html",
        {
            "products": products,
            "categories": categories,
            "units": Product.Unit.choices,
        },
    )


@producer_required
def edit_producer_product(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Invalid request method"}, status=405
        )

    try:
        data = json.loads(request.body)

        name = data.get("name", "").strip()
        if not name:
            return JsonResponse(
                {"success": False, "error": "Product name is required."}
            )

        try:
            price = float(data.get("price", 0))
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid price value."})

        base_price_value = Decimal(str(price))

        unit = data.get("unit", product.unit)
        valid_units = {choice[0] for choice in Product.Unit.choices}
        if unit not in valid_units:
            return JsonResponse({"success": False, "error": "Invalid unit."})

        availability_status = data.get(
            "availability_status", product.availability_status
        )
        valid_avail = {choice[0] for choice in Product.Availability_status.choices}
        if availability_status not in valid_avail:
            return JsonResponse(
                {"success": False, "error": "Invalid availability status."}
            )

        organic = data.get(
            "organic_certification_status", product.organic_certification_status
        )
        valid_organic = {choice[0] for choice in Product.OrganicStatus.choices}
        if organic not in valid_organic:
            return JsonResponse({"success": False, "error": "Invalid organic status."})

        category_id = data.get("category_id")
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
        else:
            category = product.category

        product_type = get_or_create_inferred_product_type(
            name=name,
            category=category,
        )

        wholesale_price_raw = str(data.get("wholesale_price", "") or "").strip()
        wholesale_min_qty_raw = str(
            data.get("wholesale_min_quantity", "") or ""
        ).strip()
        wholesale_price = None
        wholesale_min_quantity = 20
        if wholesale_price_raw:
            try:
                wholesale_price = Decimal(wholesale_price_raw)
            except (TypeError, ValueError, InvalidOperation):
                return JsonResponse(
                    {"success": False, "error": "Please enter a valid wholesale price."}
                )

            if wholesale_price <= 0:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Wholesale price must be greater than 0.",
                    }
                )

            if wholesale_price > base_price_value:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Wholesale price cannot be higher than the base price.",
                    }
                )

            if wholesale_min_qty_raw:
                try:
                    wholesale_min_quantity = int(wholesale_min_qty_raw)
                except (TypeError, ValueError):
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Please enter a valid minimum wholesale quantity.",
                        }
                    )
                if wholesale_min_quantity < 2:
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Minimum wholesale quantity must be at least 2.",
                        }
                    )

            stock_total = (
                product.inventory_batches.aggregate(
                    total=Sum("remaining_quantity")
                ).get("total")
                or 0
            )
            # Hannah removed this as why block changing wholesale quantity if current stock is low?
            # if stock_total < wholesale_min_quantity:
            #     return JsonResponse(
            #         {
            #             "success": False,
            #             "error": f"At least {wholesale_min_quantity} items in stock are required to set a wholesale price.",
            #         }
            #     )

        # Low stock threshold
        low_stock_raw = data.get("low_stock_threshold")

        try:
            low_stock_threshold = int(low_stock_raw)
            if low_stock_threshold < 0 or low_stock_threshold > 9999:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Low stock threshold must be a number between 0 and 9999.",
                }
            )

        product.name = name
        product.price = price
        product.unit = unit
        product.availability_status = availability_status
        product.organic_certification_status = organic
        product.low_stock_threshold = low_stock_threshold
        product.description = data.get("description", product.description)
        product.category = category
        product.product_type = product_type
        product.save()

        if wholesale_price is not None:
            product.product_wholesale.all().delete()
            WholesalePrice.objects.create(
                product=product,
                min_quantity=wholesale_min_quantity,
                unit_price=wholesale_price,
            )
        else:
            product.product_wholesale.all().delete()

        # Check stock vs threshold for notification
        stock_total = (
            product.inventory_batches.aggregate(total=Sum("remaining_quantity")).get(
                "total"
            )
            or 0
        )

        if stock_total <= product.low_stock_threshold:
            NotificationService.create_unique(
                user=request.user,
                type=Notification.Type.PRODUCT_ALERT,
                product=product,
                message=f"Low Stock Alert: {product.name} - only {stock_total} {product.get_unit_display()} remaining.",
            )
        else:
            NotificationService.resolve_for_product(
                product, Notification.Type.PRODUCT_ALERT
            )

        return JsonResponse(
            {
                "success": True,
                "name": product.name,
                "price": str(product.price),
                "unit_display": product.get_unit_display(),
                "unit": product.unit,
                "category": product.category.name,
                "category_id": product.category.pk,
                "product_type": (
                    product.product_type.name
                    if product.product_type
                    else product.category.name
                ),
                "product_type_id": product.product_type_id,
                "availability_status": product.availability_status,
                "availability_display": product.get_availability_status_display(),
                "organic_certification_status": product.organic_certification_status,
                "description": product.description or "",
                "wholesale_price": (
                    str(wholesale_price) if wholesale_price is not None else ""
                ),
                "wholesale_min_quantity": (
                    wholesale_min_quantity if wholesale_price is not None else ""
                ),
                "low_stock_threshold": product.low_stock_threshold,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data."}, status=400
        )


@producer_required
def cancel_producer_product(request, pk):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Invalid request method"}, status=405
        )

    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)
    product.availability_status = Product.Availability_status.DISCONTINUED
    product.save(update_fields=["availability_status"])

    return JsonResponse(
        {
            "success": True,
            "availability_status": product.availability_status,
            "availability_display": product.get_availability_status_display(),
        }
    )


def add_to_cart(request, product_id):
    print(f"TODO: Logic to add product {product_id} to the cart session.")
    return redirect("product_view", category_id=0)


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
            p.product_wholesale.order_by("min_quantity").values(
                "min_quantity", "unit_price"
            )
        )
        ctx["wholesale_tiers"] = tiers

        batch = p.inventory_batches.order_by("expiry_date").first()
        ctx["stock"] = batch.remaining_quantity if batch else 0
        ctx["expiry"] = batch.expiry_date if batch else None
        ctx["batch"] = batch

        return ctx

    # return redirect('products_list')


# Harminder Edits


def send_for_approval(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    product = Product.objects.get(pk=pk)

    # Only FLAGGED products can be sent for approval
    if product.status != Product.Status.FLAGGED:
        return JsonResponse(
            {"error": "Only flagged products can be sent for approval"}, status=400
        )

    product.status = Product.Status.PENDING
    product.save()

    return JsonResponse({"success": True})


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

# Commented on 29/06/2026 - 18:26
# def product_view(request, category_id):
#     # All categories except organic
#     categories = Category.objects.exclude(name__icontains="organic")
#     certified_organic = Category.objects.filter(name__icontains="organic")

#     # ALL PRODUCTS PAGE
#     if category_id == 0:
#         selected_category = None
#         products = Product.objects.filter(status="PUB")
#         show_filters = True

#     # CATEGORY PAGE
#     else:
#         selected_category = get_object_or_404(Category, id=category_id)
#         products = Product.objects.filter(status="PUB", category=selected_category)
#         show_filters = False

#     # Producer list for dropdown
#     producers = products.values_list("producer__farm_name", flat=True).distinct()

#     # Helper: earliest-expiring batch
#     def get_active_batch(product):
#         return product.inventory_batches.order_by("expiry_date").first()

#     product_json = []

#     for p in products:
#         batch = get_active_batch(p)

#         # -----------------------------
#         # DISCOUNT LOGIC (Surplus)
#         # -----------------------------
#         original_price = float(p.price)

#         if batch and batch.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE:
#             discount_percent = float(batch.surplus_discount_percentage)
#             discounted_price = float(original_price * (100 - discount_percent) / 100)
#             has_discount = True
#         else:
#             discounted_price = original_price
#             discount_percent = 0
#             has_discount = False

#         # -----------------------------
#         # BADGES
#         # -----------------------------

#         # Organic badge
#         organic = (p.organic_certification_status == Product.OrganicStatus.CERTIFIED)

#         # Local badge (farm origin matches producer name)
#         local = (p.farm_origin.lower() == p.producer.farm_name.lower())

#         # Fresh Today badge (48-hour freshness window)
#         if batch:
#             days_old = (date.today() - batch.harvest_date).days
#             fresh_today = days_old <= 1
#         else:
#             fresh_today = False

#         # Low stock badge
#         low_stock = (batch.remaining_quantity <= p.low_stock_threshold) if batch else False

#         # -----------------------------
#         # BUILD JSON ENTRY
#         # -----------------------------
#         product_json.append({
#             "id": p.id,
#             "name": p.name,
#             "description": p.description or "",
#             "price": discounted_price,
#             "original_price": original_price,
#             "has_discount": has_discount,
#             "discount_percent": discount_percent,

#             "organic": organic,
#             "local": local,
#             "fresh_today": fresh_today,
#             "low_stock": low_stock,

#             "image": p.image.url if p.image else "",
#             "producer": p.producer.farm_name,
#             "category": p.category.name,

#             "stock": batch.remaining_quantity if batch else 0,
#             "expiry": batch.expiry_date.strftime("%Y-%m-%d") if batch else "",
#         })

#     return render(request, "products/product_view.html", {
#         "categories": categories,
#         "producers": producers,
#         "products_json": json.dumps(product_json),
#         "selected_category": selected_category,
#         "show_filters": show_filters,
#         "organic": certified_organic,
#     })

# Updated on 30/06/2026 - 14:00 - Added search, filter, sort, pagination, wholesale visibility, and performance optimizations


def _can_view_wholesale_prices(user):
    """
    Return True when the logged-in customer is allowed to see wholesale pricing.

    User.role is usually CUSTOMER for all customer accounts. The business or
    community-group distinction is stored on Customer.organisation_type.
    """
    if not user.is_authenticated:
        return False

    customer = getattr(user, "customer_profile", None)

    if not customer:
        return False

    return customer.organisation_type in {
        "BUSINESS",
        "COMMUNITY_GROUP",
    }


NO_ALLERGENS_FILTER = "__none__"


def product_view(request, category_id):
    categories = Category.objects.exclude(name__icontains="organic")
    certified_organic = Category.objects.filter(name__icontains="organic")
    today = timezone.localdate()

    can_view_wholesale = _can_view_wholesale_prices(request.user)

    search_query = (request.GET.get("q") or "").strip()
    category_filter = (request.GET.get("category") or "").strip()
    producer_filter = (request.GET.get("producer") or "").strip()
    allergen_filter = (request.GET.get("allergen") or "").strip()
    min_price = (request.GET.get("min_price") or "").strip()
    max_price = (request.GET.get("max_price") or "").strip()
    sort = (request.GET.get("sort") or "").strip()

    live_product_filters = {
        "status": Product.Status.PUBLISHED,
        "availability_status": Product.Availability_status.AVAILABLE,
        "inventory_batches__status": Inventory.BatchStatus.ACTIVE,
        "inventory_batches__remaining_quantity__gt": 0,
        "inventory_batches__expiry_date__gte": today,
    }

    if category_id == 0:
        selected_category = None
        products_qs = Product.objects.filter(**live_product_filters).distinct()
        show_filters = True
    else:
        selected_category = get_object_or_404(Category, id=category_id)
        products_qs = Product.objects.filter(
            **live_product_filters,
            category=selected_category,
        ).distinct()
        show_filters = False

    producers = (
        products_qs.values_list("producer__farm_name", flat=True)
        .exclude(producer__farm_name__isnull=True)
        .exclude(producer__farm_name="")
        .distinct()
        .order_by("producer__farm_name")
    )

    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query)
            | Q(product_type__name__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(producer__farm_name__icontains=search_query)
        ).annotate(
            search_rank=Case(
                When(name__iexact=search_query, then=Value(1)),
                When(product_type__name__iexact=search_query, then=Value(2)),
                When(name__istartswith=search_query, then=Value(3)),
                When(product_type__name__istartswith=search_query, then=Value(4)),
                When(name__icontains=search_query, then=Value(5)),
                When(product_type__name__icontains=search_query, then=Value(6)),
                When(category__name__iexact=search_query, then=Value(7)),
                When(category__name__icontains=search_query, then=Value(8)),
                When(description__icontains=search_query, then=Value(9)),
                When(producer__farm_name__icontains=search_query, then=Value(10)),
                default=Value(99),
                output_field=IntegerField(),
            )
        )

    if show_filters and category_filter:
        products_qs = products_qs.filter(category__name=category_filter)

    if show_filters and producer_filter:
        products_qs = products_qs.filter(producer__farm_name=producer_filter)

    real_allergen_codes = [
        code
        for code, _label in Allergen.Allergens.choices
        if code != Allergen.Allergens.NONE
    ]

    if show_filters and allergen_filter == NO_ALLERGENS_FILTER:
        products_qs = products_qs.exclude(
            product_allergen__allergen__name__in=real_allergen_codes
        ).distinct()

    elif show_filters and allergen_filter in real_allergen_codes:
        products_qs = products_qs.filter(
            product_allergen__allergen__name=allergen_filter
        ).distinct()

    try:
        if min_price:
            products_qs = products_qs.filter(price__gte=Decimal(min_price))
    except InvalidOperation:
        min_price = ""

    try:
        if max_price:
            products_qs = products_qs.filter(price__lte=Decimal(max_price))
    except InvalidOperation:
        max_price = ""

    if sort == "price_low":
        order_by = ("price", "id")
    elif sort == "price_high":
        order_by = ("-price", "id")
    elif sort == "oldest":
        order_by = ("created_at", "id")
    else:
        sort = "newest"
        order_by = ("-created_at", "-id")

    if search_query:
        order_by = ("search_rank", *order_by)

    products = (
        products_qs.select_related("producer", "category", "product_type")
        .prefetch_related(
            Prefetch(
                "inventory_batches",
                queryset=Inventory.objects.filter(
                    status=Inventory.BatchStatus.ACTIVE,
                    remaining_quantity__gt=0,
                    expiry_date__gte=today,
                ).order_by("expiry_date"),
                to_attr="active_inventory_batches",
            ),
            Prefetch(
                "product_wholesale",
                queryset=WholesalePrice.objects.order_by("min_quantity"),
                to_attr="wholesale_tiers",
            ),
            "product_allergen__allergen",
        )
        .order_by(*order_by)
    )
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    product_json = []

    for p in page_obj.object_list:
        live_batches = getattr(p, "active_inventory_batches", [])

        total_live_stock = sum(batch.remaining_quantity for batch in live_batches)
        earliest_live_batch = live_batches[0] if live_batches else None

        if not earliest_live_batch or total_live_stock <= 0:
            continue

        surplus_batch = next(
            (
                batch
                for batch in live_batches
                if batch.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE
                and batch.surplus_discount_percentage
                and batch.surplus_discount_percentage > 0
            ),
            None,
        )

        is_surplus_active = surplus_batch is not None

        wholesale_tiers = getattr(p, "wholesale_tiers", [])
        active_wholesale_tier = wholesale_tiers[0] if wholesale_tiers else None

        is_wholesale_active = can_view_wholesale and active_wholesale_tier is not None

        low_stock = (
            p.low_stock_threshold is not None
            and p.low_stock_threshold > 0
            and total_live_stock <= p.low_stock_threshold
        )

        original_price = float(p.price)

        if is_surplus_active:
            discounted_price = float(surplus_batch.get_discounted_price())
            discount_percent = float(surplus_batch.surplus_discount_percentage)
            has_discount = True
        else:
            discounted_price = original_price
            discount_percent = 0
            has_discount = False

        organic = p.organic_certification_status == Product.OrganicStatus.CERTIFIED

        producer_name = p.producer.farm_name or ""
        farm_origin = p.farm_origin or ""
        local = farm_origin.strip().lower() == producer_name.strip().lower()

        days_old = (today - earliest_live_batch.harvest_date).days
        fresh_today = days_old <= 1
        allergen_names = list(
            dict.fromkeys(
                product_allergen.allergen.get_name_display()
                for product_allergen in p.product_allergen.all()
                if product_allergen.allergen
                and product_allergen.allergen.name != Allergen.Allergens.NONE
            )
        )

        product_json.append(
            {
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
                "surplus_active": is_surplus_active,
                "wholesale_active": is_wholesale_active,
                "wholesale_min_quantity": (
                    active_wholesale_tier.min_quantity if is_wholesale_active else None
                ),
                "allergens": allergen_names,
                "is_disabled": False,
                "disabled_reason": "",
                "image": p.image.url if p.image else "",
                "producer": producer_name,
                "category": p.category.name,
                "stock": total_live_stock,
                "expiry": earliest_live_batch.expiry_date.strftime("%Y-%m-%d"),
            }
        )

    query_params = request.GET.copy()
    query_params.pop("page", None)
    pagination_query = query_params.urlencode()

    return render(
        request,
        "products/product_view.html",
        {
            "categories": categories,
            "producers": producers,
            "allergens": Allergen.objects.exclude(
                name=Allergen.Allergens.NONE
            ).order_by("name"),
            "products_json": json.dumps(product_json),
            "selected_category": selected_category,
            "show_filters": show_filters,
            "organic": certified_organic,
            "page_obj": page_obj,
            "pagination_query": pagination_query,
            "filters": {
                "q": search_query,
                "category": category_filter,
                "producer": producer_filter,
                "allergen": allergen_filter,
                "min_price": min_price,
                "max_price": max_price,
                "sort": sort,
            },
        },
    )


# Product Detail page
def product_detail_page(request, product_id):
    return render(request, "products/product_detail.html", {"product_id": product_id})
