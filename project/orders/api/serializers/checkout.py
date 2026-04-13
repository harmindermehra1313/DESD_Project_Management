from rest_framework import serializers
import re

UK_POSTCODE_REGEX = re.compile(
    r"^(GIR ?0AA|"
    r"(?:(?:[A-PR-UWYZ][0-9][0-9]?|"
    r"[A-PR-UWYZ][A-HK-Y][0-9][0-9]?|"
    r"[A-PR-UWYZ][0-9][A-HJKPSTUW]|"
    r"[A-PR-UWYZ][A-HK-Y][0-9][ABEHMNPRVWXY]))"
    r" ?[0-9][ABD-HJLNP-UW-Z]{2})$",
    re.IGNORECASE
)

PHONE_REGEX = re.compile(r"^\+?\d{7,15}$")  # simple, international-safe
NAME_REGEX = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,}$")

class CheckoutSerializer(serializers.Serializer):
    is_guest = serializers.BooleanField()

    # Logged-in user fields
    delivery_address_id = serializers.IntegerField(required=False, allow_null=True)
    billing_address_id = serializers.IntegerField(required=False, allow_null=True)

    # Payment & instructions
    payment_method = serializers.CharField()
    special_instructions = serializers.CharField(required=False, allow_blank=True)

    # Guest identity
    guest_name = serializers.CharField(required=False, allow_blank=True)
    guest_email = serializers.EmailField(required=False, allow_blank=True)
    guest_phone = serializers.CharField(required=False, allow_blank=True)

    # Guest delivery address
    guest_delivery_line1 = serializers.CharField(required=False, allow_blank=True)
    guest_delivery_line2 = serializers.CharField(required=False, allow_blank=True)
    guest_delivery_city = serializers.CharField(required=False, allow_blank=True)
    guest_delivery_postcode = serializers.CharField(required=False, allow_blank=True)

    # Guest billing address
    guest_billing_line1 = serializers.CharField(required=False, allow_blank=True)
    guest_billing_line2 = serializers.CharField(required=False, allow_blank=True)
    guest_billing_city = serializers.CharField(required=False, allow_blank=True)
    guest_billing_postcode = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)

        # Pass through dynamic producer fields including recurring fields
        for key, value in data.items():
            if key.startswith((
                "delivery_or_collection_", 
                "delivery_date_", 
                "delivery_time_",
                "is_recurring_",
                "recurrence_pattern_",
                "recurrence_day_",
            )):
                validated[key] = value

        return validated
    
    def validate_guest_name(self, value):
        if value and not NAME_REGEX.match(value):
            raise serializers.ValidationError("Enter a valid name.")
        return value

    def validate_guest_phone(self, value):
        if value and not PHONE_REGEX.match(value):
            raise serializers.ValidationError("Enter a valid phone number.")
        return value

    def validate_guest_delivery_postcode(self, value):
        if value and not UK_POSTCODE_REGEX.match(value):
            raise serializers.ValidationError("Enter a valid UK postcode.")
        return value

    def validate_guest_billing_postcode(self, value):
        if value and not UK_POSTCODE_REGEX.match(value):
            raise serializers.ValidationError("Enter a valid UK postcode.")
        return value

    def validate(self, data):
        is_guest = data.get("is_guest")

        # -----------------------------
        # Logged-in user validation
        # -----------------------------
        if not is_guest:
            if not data.get("delivery_address_id"):
                raise serializers.ValidationError(
                    {"delivery_address_id": "A delivery address must be selected."}
                )

            if not data.get("billing_address_id"):
                raise serializers.ValidationError(
                    {"billing_address_id": "A billing address must be selected."}
                )

            return data

        # -----------------------------
        # Guest validation
        # -----------------------------
        required_guest_fields = [
            "guest_name",
            "guest_email",
            "guest_phone",
            "guest_delivery_line1",
            "guest_delivery_city",
            "guest_delivery_postcode",
            "guest_billing_line1",
            "guest_billing_city",
            "guest_billing_postcode",
        ]

        missing = [f for f in required_guest_fields if not data.get(f)]
        if missing:
            raise serializers.ValidationError(
                {"guest_fields": f"Missing required guest fields: {', '.join(missing)}"}
            )

        # Additional cross-field validation
        if data.get("guest_email") and "@" not in data["guest_email"]:
            raise serializers.ValidationError({"guest_email": "Enter a valid email address."})

        return data