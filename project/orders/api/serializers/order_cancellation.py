from rest_framework import serializers


class CustomerOrderCancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    
class CustomerOrderItemCancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )