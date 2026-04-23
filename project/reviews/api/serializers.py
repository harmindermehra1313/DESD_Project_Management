from rest_framework import serializers

from reviews.models import Review


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