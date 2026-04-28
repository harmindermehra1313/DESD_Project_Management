from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from reviews.models import Review

from reviews.api.serializers import ReviewCreateSerializer, PublicReviewSerializer

from products.models import Product
from reviews.selectors import (
    get_published_review_summary_for_product,
    get_published_reviews_for_product,
)


class ReviewCreateAPIView(generics.CreateAPIView):
    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()

        if review.status == Review.Status.PUBLISHED:
            code = "review_submitted"
            message = "Review submitted successfully."
        else:
            code = "review_submitted_for_moderation"
            message = "Review submitted and sent for moderation."

        return Response(
            {
                "code": code,
                "message": message,
                "status": review.status,
                "is_flagged": review.status == Review.Status.FLAGGED,
                "product_id": review.product_id,
                "review": PublicReviewSerializer(review).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProductReviewListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id: int):
        if not Product.objects.filter(pk=product_id).exists():
            return Response(
                {
                    "code": "review_product_not_found",
                    "message": "The selected product could not be found.",
                    "data": {
                        "product_id": product_id,
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

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
