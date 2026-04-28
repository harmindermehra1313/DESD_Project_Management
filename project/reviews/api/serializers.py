from rest_framework import serializers

from reviews.models import Review
from reviews.selectors import get_reviewable_order_item_for_user
from reviews.services.review_services import (
    ReviewSubmissionError,
    create_review_for_order_item,
)
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from rest_framework.exceptions import ValidationError


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
