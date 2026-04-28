from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from BRFN.decorators import admin_required, producer_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from django.urls import reverse
from .models import Recipe, FarmStory, RecipeProduct
from .forms import RecipeForm, FarmStoryForm
from accounts.models import Producer
from products.models import Product


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
    return render(request, "community/recipe_detail.html", {
        "recipe": recipe,
        "linked_products": linked_products,
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
