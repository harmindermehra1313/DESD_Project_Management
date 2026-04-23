from rest_framework import serializers

from reviews.models import Review
from reviews.selectors import get_reviewable_order_item_for_user
from reviews.services import create_review_for_order_item

class ReviewCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(required=False)
    order_item_id = serializers.IntegerField()
    product_id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=120)
    text = serializers.CharField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    anonymous = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        request = self.context["request"]

        order_item = get_reviewable_order_item_for_user(
            user_id=request.user.id,
            order_item_id=attrs["order_item_id"],
            order_id=attrs.get("order_id"),
            product_id=attrs.get("product_id"),
        )

        attrs["order_item"] = order_item
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        order_item = validated_data["order_item"]

        cleaned_data = {
            "title": validated_data["title"].strip(),
            "text": validated_data["text"].strip(),
            "rating": validated_data["rating"],
            "anonymous": validated_data.get("anonymous", False),
        }

        return create_review_for_order_item(
            user=request.user,
            order_item=order_item,
            cleaned_data=cleaned_data,
        )

class PublicReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="public_reviewer_name", read_only=True)
    verified_purchase = serializers.SerializerMethodField()
    reviewer_label = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "title",
            "text",
            "rating",
            "anonymous",
            "reviewer_name",
            "reviewer_label",
            "verified_purchase",
            "created_at",
        )
        read_only_fields = fields

    def get_verified_purchase(self, obj):
        # Under the current Review model validation, public reviews are tied
        # to real orders and shipped order items.
        return True

    def get_reviewer_label(self, obj):
        return "Anonymous" if obj.anonymous else "Named reviewer"