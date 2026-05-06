from rest_framework import serializers

from reviews.models import Review
from reviews.selectors import get_reviewable_order_item_for_user, get_producer_profile_for_user
from reviews.services.review_services import (
    ReviewSubmissionError,
    create_review_for_order_item,
)
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from rest_framework.exceptions import ValidationError
from reviews.models import ReviewProducerResponse
from reviews.services.producer_response_service import (
    ProducerResponseError,
    create_or_update_producer_response,
)


def structured_review_error(
    *,
    code: str,
    message: str,
    data: dict | None = None,
) -> ValidationError:
    return ValidationError(
        {
            "code": code,
            "message": message,
            "data": data or {},
        }
    )


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

        try:
            order_item = get_reviewable_order_item_for_user(
                user_id=request.user.id,
                order_item_id=attrs["order_item_id"],
                order_id=attrs.get("order_id"),
                product_id=attrs.get("product_id"),
            )
        except PermissionDenied as exc:
            raise structured_review_error(
                code="review_not_allowed",
                message="This review cannot be submitted for the selected order item.",
                data={
                    "order_id": attrs.get("order_id"),
                    "order_item_id": attrs.get("order_item_id"),
                    "product_id": attrs.get("product_id"),
                    "reason": str(exc),
                },
            ) from exc
        except ObjectDoesNotExist as exc:
            raise structured_review_error(
                code="review_order_item_not_found",
                message="The selected order item could not be found.",
                data={
                    "order_id": attrs.get("order_id"),
                    "order_item_id": attrs.get("order_item_id"),
                    "product_id": attrs.get("product_id"),
                },
            ) from exc
        except ValidationError:
            raise
        except Exception as exc:
            raise structured_review_error(
                code="review_item_not_eligible",
                message="This item is no longer eligible for review.",
                data={
                    "order_id": attrs.get("order_id"),
                    "order_item_id": attrs.get("order_item_id"),
                    "product_id": attrs.get("product_id"),
                    "reason": str(exc),
                },
            ) from exc

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

        try:
            return create_review_for_order_item(
                user=request.user,
                order_item=order_item,
                cleaned_data=cleaned_data,
            )
        except ReviewSubmissionError as exc:
            raise ValidationError(exc.detail) from exc

class PublicProducerResponseSerializer(serializers.ModelSerializer):
    producer_name = serializers.SerializerMethodField()

    class Meta:
        model = ReviewProducerResponse
        fields = (
            "id",
            "text",
            "producer_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_producer_name(self, obj):
        producer = getattr(obj.review.product, "producer", None)

        if producer:
            return str(producer)

        return "Producer"
class PublicReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="public_reviewer_name", read_only=True)
    verified_purchase = serializers.SerializerMethodField()
    reviewer_label = serializers.SerializerMethodField()
    producer_response = serializers.SerializerMethodField()

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
            "producer_response",
        )
        read_only_fields = fields

    def get_verified_purchase(self, obj):
        return True

    def get_reviewer_label(self, obj):
        return "Anonymous" if obj.anonymous else "Named reviewer"

    def get_producer_response(self, obj):
        response = getattr(obj, "producer_response", None)

        if not response:
            return None

        if response.status != ReviewProducerResponse.Status.PUBLISHED:
            return None

        return PublicProducerResponseSerializer(response).data
    

class ProducerReviewListSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    reviewer_name = serializers.CharField(source="public_reviewer_name", read_only=True)
    latest_activity_at = serializers.DateTimeField(read_only=True)
    producer_response = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "product_id",
            "product_name",
            "title",
            "text",
            "rating",
            "anonymous",
            "reviewer_name",
            "created_at",
            "latest_activity_at",
            "producer_response",
        )
        read_only_fields = fields

    def get_producer_response(self, obj):
        response = getattr(obj, "producer_response", None)

        if not response:
            return None

        return {
            "id": response.id,
            "text": response.text,
            "status": response.status,
            "created_at": response.created_at,
            "updated_at": response.updated_at,
        }


class ProducerResponseWriteSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)

    def validate_text(self, value):
        cleaned_value = value.strip()

        if not cleaned_value:
            raise structured_review_error(
                code="producer_response_text_required",
                message="Enter a response before submitting.",
                data={},
            )

        return cleaned_value

    def save(self, **kwargs):
        request = self.context["request"]
        review = self.context["review"]

        producer = get_producer_profile_for_user(request.user)

        if producer is None:
            raise structured_review_error(
                code="producer_profile_required",
                message="A producer profile is required to respond to reviews.",
                data={},
            )

        try:
            return create_or_update_producer_response(
                review=review,
                responder=request.user,
                text=self.validated_data["text"],
            )
        except ProducerResponseError as exc:
            raise ValidationError(exc.detail) from exc
