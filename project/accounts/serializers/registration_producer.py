# # Handles producer sign‑up. This creates:
# # - User (role=PRODUCER)
# # - Producer profile
# # Producers do NOT get an Address entry because farm address is stored directly on Producer.

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from accounts.models import User, Producer
from firebase_admin import auth as firebase_auth
from django_q.tasks import async_task
import re
from firebase_admin import auth as firebase_auth
from firebase_admin.auth import EmailAlreadyExistsError
from orders.services.food_miles import is_within_distance_limit

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
        # Email must be unique in Django database
        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({
                "email": "This email is already registered."
            })

        # Password match
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        # Terms accepted
        if not data["accept_terms"]:
            raise serializers.ValidationError({
                "accept_terms": "You must accept the terms."
            })

        # Password strength
        validate_password(data["password"])

        # UK phone validation
        uk_phone_pattern = r"^\+44(7\d{9}|1\d{9}|2\d{9}|3\d{9}|8\d{9}|55\d{8}|56\d{8})$"

        if not re.match(uk_phone_pattern, data["phone"]):
            raise serializers.ValidationError({
                "phone": "Enter a valid UK phone number starting with +44."
            })

        if not re.match(uk_phone_pattern, data["contact_phone"]):
            raise serializers.ValidationError({
                "contact_phone": "Enter a valid UK business phone number starting with +44."
            })

        # UK postcode validation
        uk_postcode_pattern = r"^([Gg][Ii][Rr] 0[Aa]{2}|(?!.*[CIKMOV])[A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s?[0-9][A-Za-z]{2})$"

        farm_postcode = data.get("farm_postcode", "").strip().upper()

        if not re.match(uk_postcode_pattern, farm_postcode):
            raise serializers.ValidationError({
                "farm_postcode": "Enter a valid UK postcode."
            })

        data["farm_postcode"] = farm_postcode

        # 20-mile Bristol radius check
        if not is_within_distance_limit(farm_postcode, max_miles=20.0):
            raise serializers.ValidationError({
                "farm_postcode": "Farm must be within 20 miles of Bristol city centre to register."
            })

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
        # firebase_auth.create_user(
        #     email=validated_data["email"],
        #     password=validated_data["password"]
        # )

        try:
            firebase_auth.create_user(
                email=validated_data["email"],
                password=validated_data["password"]
            )
        except EmailAlreadyExistsError:
            raise serializers.ValidationError({
                "email": "This email is already registered in Firebase."
            })
        async_task("accounts.tasks.send_welcome_email", user)

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