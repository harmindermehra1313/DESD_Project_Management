from orders.api.serializers.checkout import CheckoutSerializer

def validate_checkout_session(checkout_data):
    serializer = CheckoutSerializer(data=checkout_data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data