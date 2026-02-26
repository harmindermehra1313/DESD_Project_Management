from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

# Create your views here.
def register(request):
    return render(request, "accounts/register.html")

def login(request):
    return render(request, "accounts/login.html")

class UnifiedRegistrationView(APIView):
    def post(self, request):
        role = request.data.get("role", "").lower()

        if role == "producer":
            serializer = ProducerRegistrationSerializer(data=request.data)
        else:
            serializer = CustomerRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": f"{role.capitalize()} registered successfully"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# TBC - loads placeholder form based on selected role but doesn't save anything
# def register(request):
#     role = request.GET.get("role", "customer")

#     if request.method == "POST":
#         # TBC - save, currently print
#         print("Received POST for role:", request.POST.get("role"))
#         print("Form data:", request.POST)
#         return render(request, "accounts/register_success.html")

#     return render(request, "accounts/register.html", {
#         "role": role,
#     })