from rest_framework import serializers

class CheckoutSerializer(serializers.Serializer):
    # # Payment method
    # payment_method = serializers.ChoiceField(
    #     choices=Payment.Method.choices
    # )

    # # Delivery or collection
    # delivery_or_collection = serializers.ChoiceField(
    #     choices=Order.DeliveryOrCollection.choices
    # )

    # # Delivery date
    # delivery_date = serializers.DateTimeField()

    # # Optional field
    # special_instructions = serializers.CharField(
    #     allow_blank=True,
    #     required=False
    # )
    delivery_address_id = serializers.IntegerField()
    payment_method = serializers.CharField()
    special_instructions = serializers.CharField(
        required=False, 
        allow_blank=True
        )

    # Dynamic fields for each producer
    def to_internal_value(self, data):
        validated = super().to_internal_value(data)

        for key, value in data.items():
            if key.startswith("delivery_or_collection_"):
                validated[key] = value
            if key.startswith("delivery_date_"):
                validated[key] = value
            if key.startswith("delivery_time_"):
                validated[key] = value

        return validated
