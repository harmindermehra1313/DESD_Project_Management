from rest_framework import viewsets
from accounts.models import User, Address, Producer, Admin, Customer
from api.serializers.accounts import (
    UserSerializer,
    AddressSerializer,
    ProducerSerializer,
    AdminSerializer,
    CustomerSerializer,
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# class AddressViewSet(viewsets.ModelViewSet):
#     queryset = Address.objects.all()
#     serializer_class = AddressSerializer
class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer

    def initial(self, request, *args, **kwargs):
        # TBC remove fake user!
        request.user = User.objects.get(email="mark42@hotmail.com")
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # If setting new default, unset old defaults
        is_default_delivery = serializer.validated_data.get("is_default_delivery", False)
        is_default_billing = serializer.validated_data.get("is_default_billing", False)

        if is_default_delivery:
            Address.objects.filter(
                user=self.request.user,
                is_default_delivery=True
            ).update(is_default_delivery=False)

        if is_default_billing:
            Address.objects.filter(
                user=self.request.user,
                is_default_billing=True
            ).update(is_default_billing=False)

        serializer.save(user=self.request.user)

class ProducerViewSet(viewsets.ModelViewSet):
    queryset = Producer.objects.all()
    serializer_class = ProducerSerializer

class AdminViewSet(viewsets.ModelViewSet):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer