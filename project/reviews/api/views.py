from django.core.exceptions import ObjectDoesNotExist
from rest_framework import generics, permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from reviews.api.serializers import (
    ProducerResponseWriteSerializer,
    ProducerReviewListSerializer,
    PublicProducerResponseSerializer,
    PublicReviewSerializer,
    ReviewCreateSerializer,
)
from reviews.models import Review, ReviewProducerResponse
from reviews.selectors import (
    get_producer_owned_review_or_404,
    get_producer_profile_for_user,
    get_published_review_summary_for_product,
    get_published_reviews_for_product,
    get_reviews_for_producer,
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

class ProducerReviewListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        producer = get_producer_profile_for_user(request.user)

        if producer is None:
            return Response(
                {
                    "code": "producer_profile_required",
                    "message": "A producer profile is required to view producer reviews.",
                    "data": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        reviews = get_reviews_for_producer(producer=producer)
        serializer = ProducerReviewListSerializer(reviews, many=True)

        return Response(
            {
                "results": serializer.data,
            }
        )


class ProducerReviewResponseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, review_id: int):
        return self._save_response(request, review_id)

    def patch(self, request, review_id: int):
        return self._save_response(request, review_id)

    def _save_response(self, request, review_id: int):
        producer = get_producer_profile_for_user(request.user)

        if producer is None:
            return Response(
                {
                    "code": "producer_profile_required",
                    "message": "A producer profile is required to respond to reviews.",
                    "data": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            review = get_producer_owned_review_or_404(
                review_id=review_id,
                producer=producer,
            )
        except ObjectDoesNotExist:
            return Response(
                {
                    "code": "producer_review_not_found",
                    "message": "The selected review could not be found for this producer.",
                    "data": {
                        "review_id": review_id,
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProducerResponseWriteSerializer(
            data=request.data,
            context={
                "request": request,
                "review": review,
            },
        )
        serializer.is_valid(raise_exception=True)
        response = serializer.save()

        if response.status == ReviewProducerResponse.Status.PUBLISHED:
            code = "producer_response_saved"
            message = "Response saved successfully."
        else:
            code = "producer_response_sent_for_moderation"
            message = "Response saved and sent for moderation."

        return Response(
            {
                "code": code,
                "message": message,
                "status": response.status,
                "review_id": review.id,
                "producer_response": PublicProducerResponseSerializer(response).data,
            },
            status=status.HTTP_200_OK,
        )