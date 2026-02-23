from rest_framework import viewsets
from reviews.models import Review, ReviewResponse
from api.serializers.reviews import (
    ReviewSerializer,
    ReviewResponseSerializer,
)

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all().order_by("-created_at")
    serializer_class = ReviewSerializer

class ReviewResponseViewSet(viewsets.ModelViewSet):
    queryset = ReviewResponse.objects.all().order_by("-created_at")
    serializer_class = ReviewResponseSerializer