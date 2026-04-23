from django.shortcuts import get_object_or_404

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from reviews.api.serializers import PublicReviewSerializer
from reviews.selectors import (
    get_published_review_summary_for_product,
    get_published_reviews_for_product,
)


class ProductReviewListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id: int):
        get_object_or_404(Product, pk=product_id)

        reviews = get_published_reviews_for_product(product_id=product_id)
        summary = get_published_review_summary_for_product(product_id=product_id)

        serializer = PublicReviewSerializer(reviews, many=True)

        return Response(
            {
                "product_id": product_id,
                "summary": summary,
                "results": serializer.data,
            }
        )