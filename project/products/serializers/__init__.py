import logging
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from ..models import Product, Inventory

logger = logging.getLogger(__name__)

class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=True)
    description = serializers.CharField(required=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.0)
    availability_status = serializers.ChoiceField(choices=Product.Availability_status.choices)

    # Dates
    harvest_date = serializers.DateField(required=True)
    expiry_type = serializers.ChoiceField(choices=Inventory.ExpiryType.choices)
    expiry_date = serializers.DateField(required=True)

    category = serializers.IntegerField(required=True)  # Single category ID
    unit = serializers.ChoiceField(choices=Product.Unit.choices)
    organic_certification_status = serializers.ChoiceField(choices=Product.OrganicStatus.choices)
    stock_quantity = serializers.IntegerField(min_value=0, required=True)

    # Optional Fields
    wholesale_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    wholesale_min_quantity = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    low_stock_threshold = serializers.IntegerField(min_value=0, default=0, required=False)
    storage_guidance = serializers.CharField(required=False, allow_blank=True)

    # Image validation (prevents .exe, requires valid image format)
    image = serializers.ImageField(required=False, allow_null=True)

    allergen = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_price(self, value):
        logger.warning(f"[SERIALIZER CREATE RECEIVED] raw price value = {value} ({type(value)})")
        if value is None:
            raise serializers.ValidationError("Price is required.")

        try:
            dec = Decimal(str(value))
        except InvalidOperation:
            raise serializers.ValidationError("Invalid price format.")

        if dec < Decimal("0"):
            raise serializers.ValidationError("Price cannot be less than 0.")
        return dec

    def validate_wholesale_price(self, value):
        if value is None:
            return value

        try:
            dec = Decimal(str(value))
        except InvalidOperation:
            raise serializers.ValidationError("Invalid wholesale price format.")

        if dec <= Decimal("0"):
            raise serializers.ValidationError("Wholesale price must be greater than 0.")
        return dec

    def validate_image(self, value):
        if value is None:
            return value

        max_size = 3 * 1024 * 1024  # 3 MB
        if value.size > max_size:
            raise serializers.ValidationError("Image file size must be 3 MB or smaller.")
        return value

    def validate(self, attrs):
        today = timezone.localdate()

        # 1. Harvest Date Validation (Max today, Min 1 month ago)
        harvest_date = attrs.get('harvest_date')
        if harvest_date:
            one_month_ago = today - timedelta(days=30)
            if harvest_date > today:
                raise serializers.ValidationError({"harvest_date": "Harvest date cannot be in the future."})
            if harvest_date < one_month_ago:
                raise serializers.ValidationError({"harvest_date": "Harvest date cannot be more than a month ago."})

        # 2. Expiry Date Validation (Min today)
        expiry_date = attrs.get('expiry_date')
        if expiry_date:
            if expiry_date < today:
                raise serializers.ValidationError({"expiry_date": "Expiry date must be today or in the future."})
            if harvest_date and harvest_date > expiry_date:
                raise serializers.ValidationError({"expiry_date": "Harvest date cannot be after expiry date."})

        # 3. Linked Wholesale Validation
        wp = attrs.get('wholesale_price')
        wmq = attrs.get('wholesale_min_quantity')
        stock = attrs.get('stock_quantity', 0)
        base_price = attrs.get('price')

        if (wp is not None and wmq is None) or (wp is None and wmq is not None):
            raise serializers.ValidationError("If you enter a wholesale price, you must enter a wholesale quantity, and vice versa.")

        if wp is not None and base_price is not None and wp > base_price:
            raise serializers.ValidationError({"wholesale_price": "Wholesale price cannot be higher than the base price."})

        if wmq is not None and stock < wmq:
            raise serializers.ValidationError({"wholesale_min_quantity": f"At least {wmq} items in stock are required to set this wholesale price."})

        return attrs
