from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponse  # Imported for the placeholder view
from .models import Product, Category
from accounts.models import Producer
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404
from .models import Product


def is_producer_or_admin(user):
    if not user.is_authenticated:
        return False

    role = str(getattr(user, "role", "")).lower()
    if role in ["producer", "admin"]:
        return True

    if hasattr(user, "producer_profile"):
        return True

    return False


def product_list(request):
    all_products = (
        Product.objects.filter(status=Product.Status.PUBLISHED)
        .select_related("producer")
        .prefetch_related("product_allergen__allergen")
    )
    recommended_products = all_products.order_by("-created_at")[:4]
    categories = Category.objects.all()

    context = {
        "all_products": all_products,
        "recommended_products": recommended_products,
        "categories": categories,
    }
    return render(request, "products/products_list.html", context)


@login_required
@user_passes_test(is_producer_or_admin, login_url="/accounts/login/")
def add_product(request):
    if request.method == "POST":
        name = request.POST.get("name")
        price = request.POST.get("price")
        availability_status = request.POST.get("availability_status")
        harvest_date = request.POST.get("harvest_date")
        unit = request.POST.get("unit")
        stock_quantity = request.POST.get("stock_quantity")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        food_group_code = request.POST.get("category")

        group_names = {
            "MT": "Meat",
            "DAE": "Dairy and Eggs",
            "FR": "Fruit",
            "VEG": "Vegetables",
            "SEA": "Seasonal",
        }

        category_obj, created = Category.objects.get_or_create(
            food_groups=food_group_code,
            defaults={
                "name": group_names.get(food_group_code, "Unknown Category"),
                "vat": 0.00,  # Providing a default VAT
            },
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
            surplus_discount_percentage=0.00,
        )
        return redirect("products_list")

    return render(request, "products/add_product.html")








class ProductListView(ListView):
    template_name = "products/index.html"
    context_object_name = "products"
    paginate_by = 24

    def get_queryset(self):
        return Product.objects.filter(status=Product.Status.PUBLISHED).order_by(
            "-created_at"
        )


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return (
            Product.objects.filter(status__in=["PUBLISHED", Product.Status.PUBLISHED])
            .select_related("producer", "category")
            .prefetch_related(
                "product_wholesale",
                "product_allergen__allergen",  # 👈 ADD THIS
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

        return ctx
