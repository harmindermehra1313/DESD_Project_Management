from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth import logout
from django.apps import apps
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from orders.models import ProducerOrderSummary, OrderItem
from django.db.models import Prefetch

from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

Producer = apps.get_model('accounts', 'Producer')
ProducerOrderSummary = apps.get_model('orders', 'ProducerOrderSummary')

# Create your views here.
def register(request):
    return render(request, "accounts/register.html")


def logout_view(request):
    logout(request)
    return redirect("home:index")

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
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

@login_required
def producer_dashboard(request):
    # 1. Ensure the logged-in user is actually a Producer
    if request.user.role != 'PRODUCER' or not hasattr(request.user, 'producer_profile'):
        # Redirect non-producers away from this page
        return redirect('accounts:index') 
    
    producer = request.user.producer_profile
    
    # 2. Fetch the order summaries specifically for this producer
    # select_related: Grabs the Order, User (Customer), and Address in the same SQL hit
    # prefetch_related: Grabs the items, filtering to ONLY show items belonging to this producer
    summaries = ProducerOrderSummary.objects.filter(
        producer=producer
    ).select_related(
        'order', 
        'order__user', 
        'order__delivery_address'
    ).prefetch_related(
        Prefetch(
            'order__items', 
            queryset=OrderItem.objects.filter(producer=producer).select_related('product'),
            to_attr='my_items' # Stores the filtered items in a temporary attribute
        )
    ).order_by('delivery_date') # Sorted by delivery date per acceptance criteria

    context = {
        'summaries': summaries,
    }
    
    return render(request, "accounts/producer_dashboard.html", context)


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