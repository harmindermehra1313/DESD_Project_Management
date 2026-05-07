import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, F, Sum
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Q
from BRFN.decorators import producer_required
from accounts.models import Producer
from orders.models import OrderItem, ProducerOrderSummary
from products.models import Inventory, Product

from .forms import FarmStoryForm, RecipeForm
from .models import FarmStory, FavouriteRecipe, Recipe, RecipeProduct


def index(request):
    return render(request, "community/index.html")


@login_required
@producer_required
def producer_content_dashboard(request):
    producer = request.user.producer_profile
    return render(
        request,
        "community/producer_content_dashboard.html",
        {"producer": producer},
    )


@login_required
@producer_required
def recipe_create(request):
    producer = request.user.producer_profile

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, producer=producer)

        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.producer = producer
            recipe.status = Recipe.Status_choices.PUBLISHED
            recipe.save()

            RecipeProduct.objects.filter(recipe=recipe).delete()
            for product in form.cleaned_data.get("linked_products", []):
                RecipeProduct.objects.create(recipe=recipe, product=product)

            messages.success(request, "Recipe published successfully.")
            return redirect("community:producer_content_dashboard")
    else:
        form = RecipeForm(producer=producer)

    return render(request, "community/recipe_form.html", {"form": form})


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
            producer=producer,
        )

        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.producer = producer
            recipe.status = Recipe.Status_choices.PUBLISHED
            recipe.save()

            RecipeProduct.objects.filter(recipe=recipe).delete()
            for product in form.cleaned_data.get("linked_products", []):
                RecipeProduct.objects.create(recipe=recipe, product=product)

            messages.success(request, "Recipe updated successfully.")
            return redirect("community:producer_content_dashboard")
    else:
        form = RecipeForm(instance=recipe, producer=producer)

    return render(request, "community/recipe_form.html", {"form": form})


@login_required
@producer_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        producer=request.user.producer_profile,
    )
    recipe.delete()
    messages.success(request, "Recipe deleted.")
    return redirect("community:producer_content_dashboard")


@login_required
@producer_required
def farm_story_create(request):
    producer = request.user.producer_profile

    if request.method == "POST":
        form = FarmStoryForm(request.POST, request.FILES)

        if form.is_valid():
            story = form.save(commit=False)
            story.producer = producer
            story.status = FarmStory.Status_choices.PUBLISHED
            story.save()

            messages.success(request, "Farm story published successfully.")
            return redirect("community:producer_content_dashboard")
    else:
        form = FarmStoryForm()

    return render(request, "community/farm_story_form.html", {"form": form})


@login_required
@producer_required
def farm_story_edit(request, pk):
    producer = request.user.producer_profile
    story = get_object_or_404(FarmStory, pk=pk, producer=producer)

    if request.method == "POST":
        form = FarmStoryForm(request.POST, request.FILES, instance=story)

        if form.is_valid():
            story = form.save(commit=False)
            story.producer = producer
            story.status = FarmStory.Status_choices.PUBLISHED
            story.save()

            messages.success(request, "Farm story updated successfully.")
            return redirect("community:producer_content_dashboard")
    else:
        form = FarmStoryForm(instance=story)

    return render(request, "community/farm_story_form.html", {"form": form})


@login_required
@producer_required
def farm_story_delete(request, pk):
    story = get_object_or_404(
        FarmStory,
        pk=pk,
        producer=request.user.producer_profile,
    )
    story.delete()
    messages.success(request, "Farm story deleted.")
    return redirect("community:producer_content_dashboard")


@login_required
@producer_required
def recipe_api(request, pk):
    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        producer=request.user.producer_profile,
    )

    linked_products = list(
        Product.objects.filter(product_recipes__recipe=recipe).values("id", "name")
    )

    return JsonResponse({
        "title": recipe.title,
        "meta": f"{recipe.get_seasonal_tag_display()} • {recipe.created_at:%d %b %Y}",
        "image": recipe.image.url if recipe.image else "/static/img/default-product.png",
        "description": recipe.description,
        "status": recipe.get_status_display(),
        "ingredients": recipe.ingredients or [],
        "instructions": recipe.instructions or [],
        "linked_products": linked_products,
        "edit_url": reverse("community:recipe_edit", args=[recipe.id]),
        "delete_url": reverse("community:recipe_delete", args=[recipe.id]),
    })


@login_required
@producer_required
def story_api(request, pk):
    story = get_object_or_404(
        FarmStory,
        pk=pk,
        producer=request.user.producer_profile,
    )

    return JsonResponse({
        "title": story.title,
        "meta": f"{story.created_at:%d %b %Y}",
        "image": story.image.url if story.image else "/static/img/default-product.png",
        "description": story.body,
        "status": story.get_status_display(),
        "edit_url": reverse("community:farm_story_edit", args=[story.id]),
        "delete_url": reverse("community:farm_story_delete", args=[story.id]),
    })


def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.select_related("producer"),
        pk=pk,
        status=Recipe.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    linked_products = Product.objects.filter(
        product_recipes__recipe=recipe,
        producer=recipe.producer,
    )

    user_favourites = []
    if request.user.is_authenticated:
        user_favourites = request.user.favourite_recipes.values_list(
            "recipe_id",
            flat=True,
        )

    return render(
        request,
        "community/recipe_detail.html",
        {
            "recipe": recipe,
            "linked_products": linked_products,
            "user_favourites": user_favourites,
        },
    )


def story_detail(request, pk):
    story = get_object_or_404(
        FarmStory.objects.select_related("producer"),
        pk=pk,
        status=FarmStory.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    return render(
        request,
        "community/story_detail.html",
        {
            "story": story,
            "producer": story.producer,
        },
    )


def producer_profile(request, producer_id):
    producer = get_object_or_404(
        Producer,
        pk=producer_id,
        is_approved=True,
        user__is_active=True,
    )

    recipes = producer.recipes.filter(
        status=Recipe.Status_choices.PUBLISHED,
    ).order_by("-created_at")

    stories = producer.farm_stories.filter(
        status=FarmStory.Status_choices.PUBLISHED,
    ).order_by("-created_at")

    return render(
        request,
        "community/producer_profile.html",
        {
            "producer": producer,
            "recipes": recipes,
            "stories": stories,
        },
    )


def api_product_recipes(request, product_id):
    links = (
        RecipeProduct.objects
        .filter(
            product_id=product_id,
            recipe__status=Recipe.Status_choices.PUBLISHED,
            recipe__producer__is_approved=True,
            recipe__producer__user__is_active=True,
        )
        .select_related("recipe", "recipe__producer")
    )

    data = [
        {
            "id": link.recipe.id,
            "title": link.recipe.title,
            "season": link.recipe.get_seasonal_tag_display(),
            "image": link.recipe.image.url if link.recipe.image else "/static/img/default-product.png",
        }
        for link in links
    ]

    return JsonResponse({"recipes": data})


@login_required
@producer_required
def api_producer_content(request):
    producer = request.user.producer_profile

    recipes_qs = producer.recipes.all().order_by("-created_at")[:200]
    stories_qs = producer.farm_stories.all().order_by("-created_at")[:200]

    recipes = [
        {
            "id": recipe.id,
            "title": recipe.title,
            "image": recipe.image.url if recipe.image else "/static/img/default-product.png",
            "season": recipe.get_seasonal_tag_display(),
            "status_display": recipe.get_status_display(),
            "created_at": recipe.created_at.strftime("%d %b %Y"),
            "favourite_count": recipe.favourited_by.count(),
        }
        for recipe in recipes_qs
    ]

    stories = [
        {
            "id": story.id,
            "title": story.title,
            "image": story.image.url if story.image else "/static/img/default-product.png",
            "status_display": story.get_status_display(),
            "created_at": story.created_at.strftime("%d %b %Y"),
        }
        for story in stories_qs
    ]

    return JsonResponse({
        "recipes_count": producer.recipes.count(),
        "stories_count": producer.farm_stories.count(),
        "published_count": (
            producer.recipes.filter(status=Recipe.Status_choices.PUBLISHED).count()
            + producer.farm_stories.filter(
                status=FarmStory.Status_choices.PUBLISHED
            ).count()
        ),
        "recipes": recipes,
        "stories": stories,
    })


@login_required
@producer_required
def api_producer_products(request):
    producer = request.user.producer_profile

    products = Product.objects.filter(
        producer=producer,
        status=Product.Status.PUBLISHED,
    ).values("id", "name")

    return JsonResponse(list(products), safe=False)


@require_http_methods(["POST"])
@login_required
@producer_required
def api_create_recipe(request):
    producer = request.user.producer_profile

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest(
            json.dumps({"detail": "Invalid JSON."}),
            content_type="application/json",
        )

    title = payload.get("title", "").strip()
    description = payload.get("description", "").strip()
    ingredients = payload.get("ingredients", [])
    instructions = payload.get("instructions", [])
    seasonal_tag = payload.get("seasonal_tag", Recipe.Seasonal_tags.ALL_YEAR)

    if not title:
        return HttpResponseBadRequest(
            json.dumps({"detail": "Title is required."}),
            content_type="application/json",
        )

    recipe = Recipe.objects.create(
        producer=producer,
        title=title,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        image=payload.get("image", "").strip() or "",
        seasonal_tag=seasonal_tag,
        status=Recipe.Status_choices.PUBLISHED,
    )

    linked = payload.get("linked_products", [])
    if linked:
        products = Product.objects.filter(producer=producer, id__in=linked)
        for product in products:
            RecipeProduct.objects.create(recipe=recipe, product=product)

    return JsonResponse({"id": recipe.id}, status=201)


@require_http_methods(["POST"])
@login_required
@producer_required
def api_create_story(request):
    producer = request.user.producer_profile

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest(
            json.dumps({"detail": "Invalid JSON."}),
            content_type="application/json",
        )

    title = payload.get("title", "").strip()
    body = payload.get("body", "").strip()

    if not title or not body:
        return HttpResponseBadRequest(
            json.dumps({"detail": "Title and body are required."}),
            content_type="application/json",
        )

    story = FarmStory.objects.create(
        producer=producer,
        title=title,
        body=body,
        image=payload.get("image", "").strip() or "",
        status=FarmStory.Status_choices.PUBLISHED,
    )

    return JsonResponse({"id": story.id}, status=201)


def contact_us(request):
    return render(
        request,
        "community/contact_us.html",
        {
            "contact_phone": "0800 00 1066",
            "contact_email": "BRFN@farmers.co.uk",
            "contact_address": "Coldharbour Lane, Bristol, BS16 1QY",
        },
    )


def about(request):
    producer_count = Producer.objects.filter(
        user__is_active=True,
        is_approved=True,
    ).count()

    active_batches = Inventory.objects.filter(
        status=Inventory.BatchStatus.ACTIVE,
    ).count()

    delivered_items = OrderItem.objects.filter(
        order__producer_summaries__producer=F("producer"),
        order__producer_summaries__status__in=[
            ProducerOrderSummary.Status.SHIPPED,
            ProducerOrderSummary.Status.COMPLETED,
        ],
    )

    avg_food_miles = delivered_items.aggregate(avg=Avg("food_miles"))["avg"]
    total_food_miles = delivered_items.aggregate(total=Sum("food_miles"))["total"]

    return render(
        request,
        "community/about_us.html",
        {
            "producer_count": producer_count,
            "active_batches": active_batches,
            "avg_food_miles": round(avg_food_miles, 1) if avg_food_miles else None,
            "total_food_miles": round(total_food_miles, 1) if total_food_miles else None,
            "radius_limit": 20,
        },
    )


def community_hub(request):
    recipes = Recipe.objects.filter(
        status=Recipe.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    season = request.GET.get("season", "")
    producer_id = request.GET.get("producer", "")
    product_id = request.GET.get("product", "")
    sort = request.GET.get("sort", "newest")
    search = request.GET.get("search", "").strip()

    if season:
        recipes = recipes.filter(seasonal_tag=season)

    if producer_id:
        recipes = recipes.filter(producer_id=producer_id)

    if product_id:
        recipes = recipes.filter(recipe_products__product_id=product_id)

    if search:
        recipes = recipes.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    if sort == "popular":
        recipes = recipes.annotate(
            fav_count=Count("favourited_by")
        ).order_by("-fav_count", "-created_at")
    else:
        recipes = recipes.order_by("-created_at")

    recipes = recipes.select_related("producer").distinct()

    paginator = Paginator(recipes, 6)
    page_obj = paginator.get_page(request.GET.get("page"))

    story_producer_id = request.GET.get("story_producer", "")
    story_search = request.GET.get("story_search", "").strip()

    stories = FarmStory.objects.filter(
        status=FarmStory.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    if story_producer_id:
        stories = stories.filter(producer_id=story_producer_id)

    if story_search:
        stories = stories.filter(
            title__icontains=story_search
        )

    stories = stories.select_related("producer").order_by("-created_at")

    story_paginator = Paginator(stories, 6)

    story_page_number = request.GET.get("story_page")

    story_page_obj = story_paginator.get_page(story_page_number)
    producers = Producer.objects.filter(
        is_approved=True,
        user__is_active=True,
    ).order_by("farm_name")

    products = Product.objects.filter(
        producer__is_approved=True,
        producer__user__is_active=True,
        status=Product.Status.PUBLISHED,
    ).order_by("name")

    return render(request, "community/index.html", {
        "featured_recipes": page_obj.object_list,
        "featured_stories": story_page_obj.object_list,
        "story_page_obj": story_page_obj,   
        "page_obj": page_obj,
        "producers": producers,
        "products": products,
        "selected_season": season,
        "selected_producer": producer_id,
        "selected_product": product_id,
        "search": search,
        "sort": sort,
        "story_producer": story_producer_id,
        "story_search": story_search,
    })


def recipe_list(request):
    recipes = Recipe.objects.filter(
        status=Recipe.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    season = request.GET.get("season")
    producer_id = request.GET.get("producer")
    product_id = request.GET.get("product")
    search = request.GET.get("search")
    sort = request.GET.get("sort", "newest")

    if season:
        recipes = recipes.filter(seasonal_tag=season)

    if producer_id:
        recipes = recipes.filter(producer_id=producer_id)

    if product_id:
        recipes = recipes.filter(recipe_products__product_id=product_id)

    if search:
        recipes = recipes.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    if sort == "popular":
        recipes = recipes.annotate(fav_count=Count("favourited_by")).order_by("-fav_count", "-created_at")
    else:
        recipes = recipes.order_by("-created_at")

    recipes = recipes.select_related("producer").distinct()

    paginator = Paginator(recipes, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    producers = Producer.objects.filter(
        is_approved=True,
        user__is_active=True,
    ).order_by("farm_name")

    products = Product.objects.filter(
        producer__is_approved=True,
        producer__user__is_active=True,
        status=Product.Status.PUBLISHED,
    ).order_by("name")

    return render(request, "community/index.html", {
        "page_obj": page_obj,
        "recipes": page_obj.object_list,
        "producers": producers,
        "products": products,
        "selected_season": season,
        "selected_producer": producer_id,
        "selected_product": product_id,
        "search": search,
        "sort": sort,
    })

def story_list(request):
    stories = FarmStory.objects.filter(
        status=FarmStory.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    producer_id = request.GET.get("producer")
    search = request.GET.get("search")

    if producer_id:
        stories = stories.filter(producer_id=producer_id)

    if search:
        stories = stories.filter(title__icontains=search)

    stories = stories.select_related("producer").order_by("-created_at")

    producers = Producer.objects.filter(
        is_approved=True,
        user__is_active=True,
    ).order_by("farm_name")

    return render(
        request,
        "community/stories.html",
        {
            "stories": stories,
            "producers": producers,
            "selected_producer": producer_id,
            "search": search,
        },
    )


@login_required
def toggle_recipe_favourite(request, pk):
    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        status=Recipe.Status_choices.PUBLISHED,
        producer__is_approved=True,
        producer__user__is_active=True,
    )

    favourite, created = FavouriteRecipe.objects.get_or_create(
        user=request.user,
        recipe=recipe,
    )

    if not created:
        favourite.delete()

    return redirect(request.META.get("HTTP_REFERER", "community:recipe_detail"))


@login_required
def favourite_recipes(request):
    favourites = (
        FavouriteRecipe.objects
        .filter(user=request.user, recipe__status=Recipe.Status_choices.PUBLISHED)
        .select_related("recipe", "recipe__producer")
        .order_by("-created_at")
    )

    return render(request, "community/favourite_recipes.html", {
        "favourites": favourites,
    })