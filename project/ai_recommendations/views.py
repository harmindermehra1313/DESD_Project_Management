import json
from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from products.models import Product

from .models import ProductInteraction
from .services.trained_services import get_trained_recommendations_for_request


@require_POST
def track_interaction(request):
    """
    Store lightweight customer-product interaction events for the
    Task 1 recommender demo.

    Expected JSON:
    {
        "product_id": 12,
        "event_type": "view"
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "ok": False,
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    product_id = payload.get("product_id")
    event_type = payload.get("event_type", ProductInteraction.EventType.VIEW)

    valid_event_types = {
        choice[0] for choice in ProductInteraction.EventType.choices
    }

    if event_type not in valid_event_types:
        return JsonResponse(
            {
                "ok": False,
                "message": "Unsupported interaction type.",
            },
            status=400,
        )

    product = get_object_or_404(Product, pk=product_id)

    if not request.session.session_key:
        request.session.create()

    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or ""

    if event_type == ProductInteraction.EventType.VIEW:
        recent_window = timezone.now() - timedelta(minutes=30)

        duplicate_query = ProductInteraction.objects.filter(
            product=product,
            event_type=event_type,
            created_at__gte=recent_window,
        )

        if user is not None:
            duplicate_query = duplicate_query.filter(user=user)
        else:
            duplicate_query = duplicate_query.filter(session_key=session_key)

        if duplicate_query.exists():
            return JsonResponse(
                {
                    "ok": True,
                    "tracked": False,
                }
            )

    ProductInteraction.objects.create(
        user=user,
        session_key=session_key,
        product=product,
        event_type=event_type,
        source=ProductInteraction.Source.WEB,
    )

    return JsonResponse(
        {
            "ok": True,
            "tracked": True,
        }
    )


@require_GET
def product_recommendations_api(request, product_id):
    """
    Return recommendations for the product detail page.
    """
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "results": [],
                "message": "Log in to see personalised recommendations.",
            }
        )

    current_product = get_object_or_404(
        Product.objects.select_related(
            "producer",
            "category",
            "product_type",
        ),
        pk=product_id,
    )

    recommendations = get_trained_recommendations_for_request(
        request=request,
        current_product=current_product,
        limit=4,
    )

    return JsonResponse(
        {
            "results": [
                _serialise_recommendation(result)
                for result in recommendations
            ]
        }
    )


def _serialise_recommendation(result):
    """
    Convert a RecommendationResult into JSON-safe response data.
    """
    product = result.product

    return {
        "id": product.pk,
        "name": product.name,
        "price": f"{product.price:.2f}",
        "unit": product.get_unit_display(),
        "image_url": product.image.url if product.image else "",
        "detail_url": _get_product_detail_url(product),
        "producer": str(product.producer),
        "category": product.category.name if product.category_id else "",
        "product_type": (
            product.product_type.name if product.product_type_id else ""
        ),
        "score": result.score,
        "reason": result.reason,
        "signals": result.signals,
    }


def _get_product_detail_url(product):
    """
    Resolve the product detail page URL without depending on one fixed URL name.
    """
    possible_url_names = [
        "products:product_detail",
        "product_detail",
        "products:detail",
    ]

    for url_name in possible_url_names:
        try:
            return reverse(url_name, args=[product.pk])
        except NoReverseMatch:
            continue

    return f"/products/{product.pk}/"