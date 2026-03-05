from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth import logout
from rest_framework_simplejwt.tokens import RefreshToken
import datetime


from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

# Create your views here.
def register(request):
    return render(request, "accounts/register.html")


def logout_view(request):
    logout(request)
    return redirect("home:index")

# def login_view(request):
#     if request.method == "POST":
#         email = request.POST.get("email", "").strip().lower()
#         password = request.POST.get("password")
#         remember = request.POST.get("remember")  

#         user = authenticate(request, username=email, password=password)

#         if user is not None:
#             login(request, user)

#             # If "Remember me" is NOT checked -> session ends when browser closes
#             if not remember:
#                 request.session.set_expiry(0)  # expires on browser close
#             else:
#                 request.session.set_expiry(60 * 60 * 24 * 1)  # 30 days

#             if user.role == "ADMIN":
#                 return redirect("home:dashboard")   # or your admin home URL
#             else:
#                 return redirect("home:index")

#         else:
#             messages.error(request, "Invalid email or password.")

#     return render(request, "accounts/login.html")

# New Login function to generate jwt tokens
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        remember = request.POST.get("remember")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            # Session expiry
            if not remember:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 1)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Store tokens in session (optional)
            request.session["jwt_access"] = access_token
            request.session["jwt_refresh"] = str(refresh)
            
            from django.utils import timezone

            # Record login time (timezone-aware)
            login_time = timezone.now()
            request.session["login_time"] = login_time.isoformat()

            # Get session expiry (already timezone-aware)
            expiry_timestamp = request.session.get_expiry_date()
            request.session["expiry_time"] = expiry_timestamp.isoformat()

            print("LOGIN TIME:", login_time)
            print("SESSION EXPIRES AT:", expiry_timestamp)

            # Calculate remaining time safely
            remaining = expiry_timestamp - login_time
            print("TIME UNTIL LOGOUT:", remaining)

            # Debug print (optional)
            print("JWT ACCESS:", access_token)

            # Redirect based on role
            if user.role == "ADMIN":
                return redirect("home:dashboard")
            else:
                return redirect("home:index")

        else:
            messages.error(request, "Invalid email or password.")

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
