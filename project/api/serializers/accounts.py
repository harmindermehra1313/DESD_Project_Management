from rest_framework import serializers
from accounts.models import User, Address, Producer, Admin, Customer

# Validation should happen here! TBC remove when added

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "role",
            "created_at",
            "is_active",
            "is_staff",
        ]
        read_only_fields = ["id", "created_at", "is_active", "is_staff"]
    
    # Validation for fields TBC this is an example
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone(self, value):
        if not value.replace("+", "").isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")
        return value

    def validate_role(self, value):
        valid_roles = ["CUSTOMER", "PRODUCER", "COMMUNITY_GROUP", "RESTAURANT", "ADMIN"]
        if value not in valid_roles:
            raise serializers.ValidationError("Invalid role.")
        return value

# class AddressSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Address
#         fields = "__all__"
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "line1",
            "line2",
            "city",
            "postcode",
            "is_default_delivery",
            "is_default_billing",
        ]
        read_only_fields = ["id"]

class ProducerSerializer(serializers.ModelSerializer):
    
    user = UserSerializer(read_only=True)

    class Meta:
        model = Producer
        fields = "__all__"

class AdminSerializer(serializers.ModelSerializer):

    user = UserSerializer(read_only=True)

    class Meta:
        model = Admin
        fields = "__all__"

class CustomerSerializer(serializers.ModelSerializer):

    user = UserSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = "__all__"