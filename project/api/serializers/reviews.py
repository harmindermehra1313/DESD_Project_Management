from rest_framework import serializers
from reviews.models import Review, ReviewResponse
from api.serializers.products import ProductInlineSerializer
from api.serializers.accounts import CustomerSerializer, ProducerSerializer, AdminSerializer, UserSerializer
from api.serializers.orders import OrderSerializer

# Validation should happen here! TBC remove when added

class ReviewSerializer(serializers.ModelSerializer):
    product = ProductInlineSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    moderated_by_admin = AdminSerializer(read_only=True)

    class Meta:
        model = Review
        fields = "__all__"

class ReviewResponseSerializer(serializers.ModelSerializer):
    review = ReviewSerializer(read_only=True)
    producer = ProducerSerializer(read_only=True)
    moderated_by_admin_id = AdminSerializer(read_only=True)

    class Meta:
        model = ReviewResponse
        fields = "__all__"