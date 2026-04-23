from rest_framework import serializers

from reviews.models import Review


class PublicReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="public_reviewer_name", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "title",
            "text",
            "rating",
            "anonymous",
            "reviewer_name",
            "created_at",
        )
        read_only_fields = fields