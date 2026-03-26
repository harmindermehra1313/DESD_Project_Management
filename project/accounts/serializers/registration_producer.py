# # Handles producer sign‑up. This creates:
# # - User (role=PRODUCER)
# # - Producer profile
# # Producers do NOT get an Address entry because farm address is stored directly on Producer.

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from accounts.models import User, Producer
from firebase_admin import auth as firebase_auth

class ProducerRegistrationSerializer(serializers.Serializer):
    # User fields
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)

    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    accept_terms = serializers.BooleanField(write_only=True)

    # Producer fields
    farm_name = serializers.CharField(max_length=150)
    farm_description = serializers.CharField(required=False, allow_blank=True)
    organic_certification_number = serializers.CharField(required=False, allow_blank=True)
    farm_postcode = serializers.CharField(max_length=20)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=20)

    payout_method = serializers.ChoiceField(
    choices=["BANK_TRANSFER", "PAYPAL", "CHEQUE"],
    required=True
    )

    bank_account_name = serializers.CharField(required=False, allow_blank=True)
    bank_account_number = serializers.CharField(required=False, allow_blank=True)
    bank_sort_code = serializers.CharField(required=False, allow_blank=True)
    paypal_email = serializers.EmailField(required=False, allow_blank=True)
    cheque_payee_name = serializers.CharField(required=False, allow_blank=True)
    cheque_postal_address = serializers.CharField(required=False, allow_blank=True)
    payout_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        if not data["accept_terms"]:
            raise serializers.ValidationError({"accept_terms": "You must accept the terms."})

        validate_password(data["password"])
        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("confirm_password")
        validated_data.pop("accept_terms")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            phone=validated_data["phone"],
            role="PRODUCER",
        )
        firebase_auth.create_user(
            email=validated_data["email"],
            password=validated_data["password"]
        )

        return Producer.objects.create(
            user=user,
            farm_name=validated_data["farm_name"],
            farm_description=validated_data.get("farm_description", ""),
            organic_certification_number=validated_data.get("organic_certification_number", ""),
            farm_postcode=validated_data["farm_postcode"],
            contact_email=validated_data["contact_email"],
            contact_phone=validated_data["contact_phone"],
            payout_method=validated_data.get("payout_method", "CHEQUE"),

            bank_account_name=validated_data.get("bank_account_name", ""),
            bank_account_number=validated_data.get("bank_account_number", ""),
            bank_sort_code=validated_data.get("bank_sort_code", ""),
            paypal_email=validated_data.get("paypal_email", ""),

            cheque_payee_name=validated_data.get("cheque_payee_name", ""),
            cheque_postal_address=validated_data.get("cheque_postal_address", ""),

            payout_notes=validated_data.get("payout_notes", ""),
        )