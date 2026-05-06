from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from BRFN.decorators import admin_required, producer_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from django.urls import reverse
from .models import Recipe, FarmStory, RecipeProduct,FavouriteRecipe
from .forms import RecipeForm, FarmStoryForm
from accounts.models import Producer
from products.models import Product
from django.db.models import Avg, Sum, F
from products.models import Inventory
from accounts.models import Producer
from orders.models import ProducerOrderSummary, OrderItem


def index(request):
    return render(request, "community/index.html")


@login_required
@producer_required
def producer_content_dashboard(request):
    """
    Renders the producer content dashboard page.
    The template is intentionally minimal (no server-side loops).
    Client-side JS will fetch lists via the JSON API.
    """
    producer = request.user.producer_profile
    # pass only minimal context required by the template
    return render(request, "community/producer_content_dashboard.html", {
        "producer": producer,
    })


@login_required
@producer_required
def recipe_create(request):
    producer = request.user.producer_profile

    if request.method == "POST":
        form = RecipeForm(
            request.POST,
            request.FILES,
            producer=producer
        )

        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.producer = producer  # ← REQUIRED
            recipe.save()

            # Save linked products
            for product in form.cleaned_data.get("linked_products", []):
                RecipeProduct.objects.create(recipe=recipe, product=product)

            messages.success(request, "Recipe created successfully.")
            return redirect("community:producer_content_dashboard")

    else:
        form = RecipeForm(producer=producer)

    return render(request, "community/recipe_form.html", {"form": form})


def recipe_api(request, pk):
    r = Recipe.objects.get(id=pk)
    linked_products = list(
    Product.objects.filter(product_recipes__recipe=r).values("id", "name"))

    return JsonResponse({
        "title": r.title,
        "meta": f"{r.get_seasonal_tag_display()} • {r.created_at:%d %b %Y}",
        "image": r.image.url if r.image else "",
        "description": r.description,
        "status": r.get_status_display(),
        "ingredients": r.ingredients,
        "instructions": r.instructions,
        "linked_products": linked_products,
        "edit_url": f"/community/recipes/{r.id}/edit/",
        "delete_url": f"/community/recipes/{r.id}/delete/",

    })

def story_api(request, pk):
    s = FarmStory.objects.get(id=pk)

    return JsonResponse({
        "title": s.title,
        "meta": f"{s.created_at:%d %b %Y}",
        "image": s.image.url if s.image else "/static/img/default-product.png",
        "description": s.body,
        "status": s.get_status_display(),
        "edit_url": reverse("community:farm_story_edit", args=[s.id]),
        "delete_url": reverse("community:farm_story_delete", args=[s.id]),
    })


@login_required
@producer_required
def recipe_edit(request, pk):
    producer = request.user.producer_profile
    recipe = get_object_or_404(Recipe, pk=pk, producer=producer)

    if request.method == "POST":
        form = RecipeForm(
            request.POST,
            request.FILES,
            instance=recipe,
            producer=producer
        )

        if form.is_valid():
            recipe = form.save()

            # Update linked products
            RecipeProduct.objects.filter(recipe=recipe).delete()
            for product in form.cleaned_data.get("linked_products", []):
                RecipeProduct.objects.create(recipe=recipe, product=product)

            messages.success(request, "Recipe updated successfully.")
            return redirect("community:producer_content_dashboard")

    else:
        # Pre-select linked products
        initial_products = Product.objects.filter(
            product_recipes__recipe=recipe
        ).values_list("id", flat=True)

        form = RecipeForm(
            instance=recipe,
            initial={"linked_products": initial_products},
            producer=producer
        )

    return render(request, "community/recipe_form.html", {"form": form})


@login_required
@producer_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, producer=request.user.producer_profile)
    recipe.delete()
    messages.success(request, "Recipe deleted.")
    return redirect("community:producer_content_dashboard")


@login_required
@producer_required
def farm_story_edit(request, pk):
    story = get_object_or_404(FarmStory, pk=pk, producer=request.user.producer_profile)

    if request.method == "POST":
        form = FarmStoryForm(request.POST, request.FILES, instance=story)
        if form.is_valid():
            form.save()
            messages.success(request, "Farm story updated.")
            return redirect("community:producer_content_dashboard")
    else:
        form = FarmStoryForm(instance=story)

    return render(request, "community/farm_story_form.html", {"form": form})


@login_required
@producer_required
def farm_story_delete(request, pk):
    story = get_object_or_404(FarmStory, pk=pk, producer=request.user.producer_profile)
    story.delete()
    messages.success(request, "Farm story deleted.")
    return redirect("community:producer_content_dashboard")


#-------------------------------------------------

@login_required
@producer_required
def farm_story_create(request):
    """
    Renders the farm story creation page. Supports POST for progressive enhancement.
    """
    producer = get_object_or_404(Producer, user=request.user)

    if request.method == "POST":
        form = FarmStoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.producer = producer
            story.save()
            messages.success(request, "Farm story published.")
            return redirect("community:producer_content_dashboard")
    else:
        form = FarmStoryForm()

    return render(request, "community/farm_story_form.html", {"form": form})


def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, status=Recipe.Status_choices.PUBLISHED)
    linked_products = Product.objects.filter(product_recipes__recipe=recipe)
     
    user_favourites = []
    if request.user.is_authenticated:
        user_favourites = request.user.favourite_recipes.values_list(
            "recipe_id", flat=True
        )

    return render(request, "community/recipe_detail.html", {
        "recipe": recipe,
        "linked_products": linked_products,
        "user_favourites": user_favourites, 
    })


def producer_profile(request, producer_id):
    producer = get_object_or_404(Producer, pk=producer_id)
    recipes = producer.recipes.filter(status=Recipe.Status_choices.PUBLISHED)
    stories = producer.farm_stories.filter(status=FarmStory.Status_choices.PUBLISHED)
    return render(request, "community/producer_profile.html", {
        "producer": producer,
        "recipes": recipes,
        "stories": stories,
    })


def api_product_recipes(request, product_id):
    """
    Existing endpoint used by product detail page to fetch linked recipes.
    Returns: { "recipes": [ {id, title, season, image}, ... ] }
    """
    links = RecipeProduct.objects.filter(
        product_id=product_id,
        recipe__status=Recipe.Status_choices.PUBLISHED
    ).select_related("recipe")

    data = [
        {
            "id": link.recipe.id,
            "title": link.recipe.title,
            "season": link.recipe.get_seasonal_tag_display(),
            "image": link.recipe.image.url if link.recipe.image else "",
        }
        for link in links
    ]

    return JsonResponse({"recipes": data})


# ---------------------------
# New JSON API endpoints used by client-side pages
# ---------------------------

@login_required
@producer_required
def api_producer_content(request):
    """
    Returns a compact summary and lists for the logged-in producer.
    Used by dashboard.js to render the page without server-side loops.
    """
    try:
        producer = request.user.producer_profile
    except Producer.DoesNotExist:
        return HttpResponseForbidden("Not a producer")

    recipes_qs = producer.recipes.all().order_by("-created_at")[:200]
    stories_qs = producer.farm_stories.all().order_by("-created_at")[:200]

    recipes = [
        {
            "id": r.id,
            "title": r.title,
            "image": r.image.url if r.image else "",
            "season": r.get_seasonal_tag_display(),
            "status_display": r.get_status_display(),
            "created_at": r.created_at.strftime("%d %b %Y"),
        }
        for r in recipes_qs
    ]

    stories = [
        {
            "id": s.id,
            "title": s.title,
            "image": s.image.url if s.image else "",
            "status_display": s.get_status_display(),
            "created_at": s.created_at.strftime("%d %b %Y"),
        }
        for s in stories_qs
    ]


    data = {
        "recipes_count": producer.recipes.count(),
        "stories_count": producer.farm_stories.count(),
        "published_count": (
            producer.recipes.filter(status=Recipe.Status_choices.PUBLISHED).count()
            + producer.farm_stories.filter(status=FarmStory.Status_choices.PUBLISHED).count()
        ),
        "recipes": recipes,
        "stories": stories,
    }
    return JsonResponse(data)


@login_required
@producer_required
def api_producer_products(request):
    """
    Returns a simple list of producer products for linking in the recipe form.
    Response: [ {id, name}, ... ]
    """
    try:
        producer = request.user.producer_profile
    except Producer.DoesNotExist:
        return HttpResponseForbidden("Not a producer")

    products = Product.objects.filter(producer=producer).values("id", "name")
    return JsonResponse(list(products), safe=False)


@require_http_methods(["POST"])
@login_required
@producer_required
def api_create_recipe(request):
    """
    Accepts JSON payload to create a recipe. Producer-scoped.
    Expected JSON:
    {
      "title": "...",
      "description": "...",
      "ingredients": ["...","..."],
      "instructions": ["...","..."],
      "seasonal_tag": "ALL",
      "image": "...",
      "linked_products": [1,2,3]
    }
    """
    try:
        producer = request.user.producer_profile
    except Producer.DoesNotExist:
        return HttpResponseForbidden("Not a producer")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    title = payload.get("title", "").strip()
    if not title:
        return HttpResponseBadRequest(json.dumps({"detail": "Title required"}), content_type="application/json")

    # create recipe
    recipe = Recipe.objects.create(
        producer=producer,
        title=title,
        description=payload.get("description", "").strip(),
        ingredients=payload.get("ingredients", []),
        instructions=payload.get("instructions", []),
        image=payload.get("image", "").strip() or "",
        seasonal_tag=payload.get("seasonal_tag", "ALL"),
        status=Recipe.Status_choices.PUBLISHED,
        created_at=timezone.now(),
    )

    # link products (only those belonging to this producer)
    linked = payload.get("linked_products", [])
    if linked:
        products = Product.objects.filter(producer=producer, id__in=linked)
        for p in products:
            RecipeProduct.objects.create(recipe=recipe, product=p)

    return JsonResponse({"id": recipe.id}, status=201)


@require_http_methods(["POST"])
@login_required
def api_create_story(request):
    """
    Accepts JSON payload to create a farm story.
    Expected JSON: { "title": "...", "body": "...", "image": "..." }
    """
    try:
        producer = request.user.producer_profile
    except Producer.DoesNotExist:
        return HttpResponseForbidden("Not a producer")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    title = payload.get("title", "").strip()
    body = payload.get("body", "").strip()
    if not title or not body:
        return HttpResponseBadRequest(json.dumps({"detail": "Title and body required"}), content_type="application/json")

    story = FarmStory.objects.create(
        producer=producer,
        title=title,
        body=body,
        image=payload.get("image", "").strip() or "",
        status=FarmStory.Status_choices.PUBLISHED,
        created_at=timezone.now(),
    )
    return JsonResponse({"id": story.id}, status=201)

def story_detail(request, pk):
    story = get_object_or_404(FarmStory, pk=pk, status=FarmStory.Status_choices.PUBLISHED)
    return render(request, "community/story_detail.html", {
        "story": story,
        "producer": story.producer,
    })


def contact_us(request):
    context = {
        "contact_phone": "0800 00 1066",
        "contact_email": "BRFN@farmers.co.uk",
        "contact_address": "Coldharbour Lane, Bristol, BS16 1QY",
    }
    return render(request, "community/contact_us.html", context)


def about(request):
    # Count active producers
    producer_count = Producer.objects.filter(user__is_active=True).count()

    # Active inventory batches
    active_batches = Inventory.objects.filter(
        status=Inventory.BatchStatus.ACTIVE
    ).count()

    # Delivered items = per-producer fulfilment
    delivered_items = OrderItem.objects.filter(
        order__producer_summaries__producer=F("producer"),
        order__producer_summaries__status__in=[
            ProducerOrderSummary.Status.SHIPPED,
            ProducerOrderSummary.Status.COMPLETED,
        ]
    )

    avg_food_miles = delivered_items.aggregate(
        avg=Avg("food_miles")
    )["avg"]

    total_food_miles = delivered_items.aggregate(
        total=Sum("food_miles")
    )["total"]

    context = {
        "producer_count": producer_count,
        "active_batches": active_batches,
        "avg_food_miles": round(avg_food_miles, 1) if avg_food_miles else None,
        "total_food_miles": round(total_food_miles, 1) if total_food_miles else None,
        "radius_limit": 20,
    }

    return render(request, "community/about_us.html", context)


# ----- Customer side 

def community_hub(request):
    # Featured Recipes (latest 3)
    featured_recipes = (
        Recipe.objects.filter(status="PUB")
        .select_related("producer")
        .order_by("-created_at")[:3]
    )

    # Featured Farm Stories (latest 3)
    featured_stories = (
        FarmStory.objects.filter(status="PUB")
        .select_related("producer")
        .order_by("-created_at")[:3]
    )

    context = {
        "featured_recipes": featured_recipes,
        "featured_stories": featured_stories,
    }

    return render(request, "community/index.html", context)


def recipe_list(request):
    recipes = Recipe.objects.filter(status=Recipe.Status_choices.PUBLISHED)

    # Filters
    season = request.GET.get("season")
    producer = request.GET.get("producer")
    search = request.GET.get("search")

    if season:
        recipes = recipes.filter(seasonal_tag=season)

    if producer:
        recipes = recipes.filter(producer_id=producer)

    if search:
        recipes = recipes.filter(title__icontains=search)

    recipes = recipes.select_related("producer").order_by("-created_at")

    producers = Producer.objects.filter(is_approved=False)


    return render(request, "community/recipes.html", {
        "recipes": recipes,
        "producers": producers,
        "selected_season": season,
        "selected_producer": producer,
        "search": search,
    })


def story_list(request):
    stories = FarmStory.objects.filter(status=FarmStory.Status_choices.PUBLISHED)

    producer = request.GET.get("producer")
    search = request.GET.get("search")

    if producer:
        stories = stories.filter(producer_id=producer)

    if search:
        stories = stories.filter(title__icontains=search)

    stories = stories.select_related("producer").order_by("-created_at")

    producers = Producer.objects.all()

    return render(request, "community/stories.html", {
        "stories": stories,
        "producers": producers,
        "selected_producer": producer,
        "search": search,
    })


@login_required
def toggle_recipe_favourite(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, status="PUB")

    fav, created = FavouriteRecipe.objects.get_or_create(
        user=request.user,
        recipe=recipe
    )

    if not created:
        fav.delete()

    return redirect(request.META.get("HTTP_REFERER", "community:recipe_detail"))
