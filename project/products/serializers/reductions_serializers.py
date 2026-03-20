from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, time
from ..models import Inventory
from django.utils.timezone import make_aware
from decimal import Decimal, InvalidOperation
import logging
logger = logging.getLogger(__name__)

class SurplusCreateSerializer(serializers.ModelSerializer):
    surplus_discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=True
    )
    surplus_expiry = serializers.DateTimeField(required=True)
    surplus_note = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
        )
    product = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = [
            "id",
            "product",
            "remaining_quantity",
            "expiry_date",
            "expiry_type",
            "surplus_status",
            "surplus_discount_percentage",
            "surplus_expiry",
            "surplus_note",
        ]
        read_only_fields = [
            "product",
            "remaining_quantity",
            "expiry_date",
            "expiry_type",
            "surplus_status",
        ]

    def validate_surplus_discount_percentage(self, value):
        logger.warning(f"[SERIALIZER CREATE RECEIVED] raw value = {value} ({type(value)})")
        if value is None:
            return value

        # Convert safely to Decimal (never float)
        try:
            dec = Decimal(str(value))
        except InvalidOperation:
            raise serializers.ValidationError("Invalid discount format.")

        logger.warning(f"[SERIALIZER CREATE PARSED] Decimal value = {dec}")

        # Range check
        if not (Decimal("1") <= dec <= Decimal("90")):
            raise serializers.ValidationError("Discount must be between 1% and 90%.")

        # Max 2 decimal places
        if dec.as_tuple().exponent < -2:
            raise serializers.ValidationError("Discount cannot have more than 2 decimal places.")

        return dec
    
    def validate_surplus_expiry(self, value):
        """
        Accepts a string, date, or datetime and normalises to 23:59:59.
        Ensures the result is timezone-aware.
        """
        batch = self.instance
        now = timezone.now()

        # If value is a string (e.g. "2026-04-24"), parse it
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD.")

        # If value is a datetime
        if isinstance(value, datetime):
            # If no time provided, normalise to 23:59:59
            if value.time() == time(0, 0):
                value = datetime.combine(value.date(), time(23, 59, 59))
        else:
            # It's a date → convert to datetime
            value = datetime.combine(value, time(23, 59, 59))

        # Make timezone-aware
        if timezone.is_naive(value):
            value = make_aware(value)

        # Must be in the future
        if value <= now:
            raise serializers.ValidationError("Deal expiry must be a future date.")

        # Cannot exceed product expiry
        if batch and value.date() > batch.expiry_date:
            raise serializers.ValidationError(
                "Deal expiry cannot exceed the product's expiry date."
            )

        return value
    
    def get_product(self, obj):
        return {
            "id": obj.product.id,
            "name": obj.product.name,
        }

class SurplusUpdateSerializer(serializers.ModelSerializer):
    surplus_discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    surplus_expiry = serializers.DateTimeField(
        required=False,
        allow_null=True
    )
    surplus_note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = Inventory
        fields = [
            "surplus_discount_percentage",
            "surplus_expiry",
            "surplus_note",
        ]

    def validate(self, attrs):
        # Allow empty payload for cancel API
        if self.context.get("view").__class__.__name__ == "SurplusCancelAPI":
            return attrs
    
        if not attrs:
            raise serializers.ValidationError(
                "You must update at least one field."
            )
        return attrs

    def validate_surplus_discount_percentage(self, value):
        logger.warning(f"[SERIALIZER UPDATE RECEIVED] raw value = {value} ({type(value)})")
        if value is None:
            return value

        # Convert safely to Decimal (never float)
        try:
            dec = Decimal(str(value))
        except InvalidOperation:
            raise serializers.ValidationError("Invalid discount format.")

        logger.warning(f"[SERIALIZER UPDATE PARSED] Decimal value = {dec}")

        # Range check
        if not (Decimal("1") <= dec <= Decimal("90")):
            raise serializers.ValidationError("Discount must be between 1% and 90%.")

        # Max 2 decimal places
        if dec.as_tuple().exponent < -2:
            raise serializers.ValidationError("Discount cannot have more than 2 decimal places.")

        return dec

    def validate_surplus_expiry(self, value):
        """
        Accepts a string, date, or datetime and normalises to 23:59:59.
        Ensures the result is timezone-aware.
        """
        batch = self.instance
        now = timezone.now()

        # If value is a string (e.g. "2026-04-24"), parse it
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD.")

        # If value is a datetime
        if isinstance(value, datetime):
            # If no time provided, normalise to 23:59:59
            if value.time() == time(0, 0):
                value = datetime.combine(value.date(), time(23, 59, 59))
        else:
            # It's a date → convert to datetime
            value = datetime.combine(value, time(23, 59, 59))

        # Make timezone-aware
        if timezone.is_naive(value):
            value = make_aware(value)

        # Must be in the future
        if value <= now:
            raise serializers.ValidationError("Deal expiry must be a future date.")

        # Cannot exceed product expiry
        if batch and value.date() > batch.expiry_date:
            raise serializers.ValidationError(
                "Deal expiry cannot exceed the product's expiry date."
            )

        return value

class SurplusOutputSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    snapshot_discount = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    snapshot_expiry = serializers.DateTimeField(required=False, allow_null=True)
    snapshot_note = serializers.CharField(required=False, allow_null=True)
    ended_at = serializers.DateTimeField(required=False, allow_null=True)
    ended_reason = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "product",
            "remaining_quantity",
            "expiry_date",
            "expiry_type",
            "surplus_status",
            "surplus_discount_percentage",
            "surplus_expiry",
            "surplus_note",
            "snapshot_discount",
            "snapshot_expiry",
            "snapshot_note",
            "ended_at",
            "ended_reason",
        ]

    def get_product(self, obj):
        return {
            "id": obj.product.id,
            "name": obj.product.name,
        }
    
    def to_representation(self, obj):
        data = super().to_representation(obj)

        # Fetch last reduction_ended event
        end_event = (
            obj.history
            .filter(event_type="reduction_ended")
            .order_by("-changed_at")
            .first()
        )

        if end_event:
            data["snapshot_discount"] = end_event.snapshot_discount
            data["snapshot_expiry"] = end_event.snapshot_expiry
            data["snapshot_note"] = end_event.snapshot_note
            data["ended_at"] = end_event.changed_at
            data["ended_reason"] = end_event.ended_reason
        else:
            data["snapshot_discount"] = None
            data["snapshot_expiry"] = None
            data["snapshot_note"] = None
            data["ended_at"] = None
            data["ended_reason"] = None

        return data