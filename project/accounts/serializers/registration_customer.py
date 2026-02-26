# # Handles customer sign‑up. This creates:
# # - User (role=CUSTOMER)
# # - Customer profile
# # - Address entry
# # All wrapped in a single atomic transaction so nothing breaks halfway.

# from rest_framework import serializers
# from django.contrib.auth.password_validation import validate_password
# from django.db import transaction
# from accounts.models import User, Customer, Address


# class CustomerRegistrationSerializer(serializers.Serializer):
#     # Basic user info
#     name = serializers.CharField(max_length=100)
#     email = serializers.EmailField()
#     phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

#     # Password fields
#     password = serializers.CharField(write_only=True)
#     confirm_password = serializers.CharField(write_only=True)
#     accept_terms = serializers.BooleanField(write_only=True)

#     # Customer type
#     customer_account_type = serializers.ChoiceField(
#         choices=["INDIVIDUAL", "BUSINESS", "COMMUNITY_GROUP"]
#     )

#     # Business fields
#     business_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
#     business_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
#     business_contact_person = serializers.CharField(max_length=150, required=False, allow_blank=True)

#     # Community fields
#     community_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
#     community_contact = serializers.CharField(max_length=150, required=False, allow_blank=True)
#     community_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)

#     # Address fields
#     line1 = serializers.CharField(max_length=255)
#     line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
#     city = serializers.CharField(max_length=100)
#     postcode = serializers.CharField(max_length=20)
#     accept_terms = serializers.BooleanField(write_only=True)

#     def validate(self, data):
#         # Check password match
#         if data["password"] != data["confirm_password"]:
#             raise serializers.ValidationError({"password": "Passwords do not match."})

#         # Check terms
#         if not data["accept_terms"]:
#             raise serializers.ValidationError({"accept_terms": "You must accept the terms."})

#         validate_password(data["password"])
#         return data

#     @transaction.atomic
#     def create(self, validated_data):
#         # Remove fields not needed for User creation
#         validated_data.pop("confirm_password")
#         validated_data.pop("accept_terms")

#         # Extract address fields
#         address_fields = {
#             "line1": validated_data.pop("line1"),
#             "line2": validated_data.pop("line2", ""),
#             "city": validated_data.pop("city"),
#             "postcode": validated_data.pop("postcode"),
#             "is_default_delivery": True,
#             "is_default_billing": True,
#         }

#         # Extract customer type
#         customer_type = validated_data.pop("customer_account_type")

#         # Create user
#         user = User.objects.create_user(
#             email=validated_data["email"],
#             password=validated_data["password"],
#             name=validated_data["name"],
#             phone=validated_data.get("phone", ""),
#             role="CUSTOMER",
#         )

#         # Create customer profile
#         Customer.objects.create(
#             user=user,
#             organisation_type=customer_type,
#             registration_number=validated_data.get("business_registration_number")
#             or validated_data.get("community_registration_number"),
#             contact_person_name=validated_data.get("business_contact_person")
#             or validated_data.get("community_contact"),
#         )

#         # Create address
#         Address.objects.create(user=user, **address_fields)

#         return user
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from accounts.models import User, Customer, Address
import re


class CustomerRegistrationSerializer(serializers.Serializer):
    # User fields
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    # Customer-specific
    customer_account_type = serializers.ChoiceField(
        choices=["INDIVIDUAL", "BUSINESS", "COMMUNITY_GROUP"]
    )

    # Business fields
    business_name = serializers.CharField(required=False, allow_blank=True)
    business_registration_number = serializers.CharField(required=False, allow_blank=True)
    business_contact_person = serializers.CharField(required=False, allow_blank=True)

    # Community fields
    community_name = serializers.CharField(required=False, allow_blank=True)
    community_contact = serializers.CharField(required=False, allow_blank=True)
    community_registration_number = serializers.CharField(required=False, allow_blank=True)

    # Address fields
    line1 = serializers.CharField()
    line2 = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField()
    postcode = serializers.CharField()

    def validate(self, data):
        # Full name must contain at least 2 words
        if len(data["name"].split()) < 2:
            raise serializers.ValidationError({"name": "Please enter your full name (first and last)."})

        # Email must be unique
        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        # Phone validation (optional)
        phone = data.get("phone")
        if phone and not re.match(r"^\+?[0-9\s\-()]{7,20}$", phone):
            raise serializers.ValidationError({"phone": "Enter a valid phone number."})

        # Password match
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Password strength
        validate_password(data["password"])

        # Account type validation
        account_type = data["customer_account_type"]

        if account_type == "BUSINESS":
            required = ["business_name", "business_registration_number", "business_contact_person"]
            for field in required:
                if not data.get(field):
                    raise serializers.ValidationError({field: "This field is required for business accounts."})

        if account_type == "COMMUNITY_GROUP":
            required = ["community_name", "community_contact", "community_registration_number"]
            for field in required:
                if not data.get(field):
                    raise serializers.ValidationError({field: "This field is required for community group accounts."})

        # Address validation
        for f in ["line1", "city", "postcode"]:
            if not data.get(f):
                raise serializers.ValidationError({f: "This field is required."})

        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("confirm_password")

        # Create user
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            role="CUSTOMER",
        )

        # Create customer profile
        customer = Customer.objects.create(
            user=user,
            organisation_type=validated_data["customer_account_type"],
            registration_number=validated_data.get("business_registration_number")
                or validated_data.get("community_registration_number"),
            contact_person_name=validated_data.get("business_contact_person")
                or validated_data.get("community_contact"),
        )

        # Create default address
        Address.objects.create(
            user=user,
            line1=validated_data["line1"],
            line2=validated_data.get("line2", ""),
            city=validated_data["city"],
            postcode=validated_data["postcode"],
            is_default_delivery=True,
            is_default_billing=True,
        )

        return customer