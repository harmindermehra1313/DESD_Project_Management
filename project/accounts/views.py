from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth import logout

from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

# Create your views here.
def register(request):
    return render(request, "accounts/register.html")


def logout_view(request):
    logout(request)
    return redirect("home:index")

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        remember = request.POST.get("remember")  

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            # If "Remember me" is NOT checked -> session ends when browser closes
            if not remember:
                request.session.set_expiry(0)  # expires on browser close
            else:
                request.session.set_expiry(60 * 60 * 24 * 1)  # 30 days

            return redirect("home:index")
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "accounts/login.html")

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