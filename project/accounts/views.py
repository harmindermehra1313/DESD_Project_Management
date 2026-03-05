import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse                   
from orders.models import ProducerOrderSummary, OrderItem
from django.db.models import Prefetch

from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

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
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 1)  # 1 day (or 30 days depending on your math)

            return redirect("home:index")
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "accounts/login.html")

@login_required
def profile(request):
    return render(request, "accounts/profile.html")

@login_required
def producer_dashboard(request):
    if request.user.role != 'PRODUCER' or not hasattr(request.user, 'producer_profile'):
        return redirect('home:index') 
    
    producer = request.user.producer_profile
    
    # Fetch ALL orders for this producer (JS handles the filtering now)
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
            to_attr='my_items'
        )
    ).order_by('delivery_date')

    # Calculate the 95% payout for each summary
    for summary in summaries:
        summary.payout_amount = float(summary.subtotal) * 0.95

    context = {
        'summaries': summaries,
    }
    
    return render(request, "accounts/producer_dashboard.html", context)

@login_required
@require_POST
def update_order_status(request, summary_id):
    if request.user.role != 'PRODUCER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        valid_statuses = ['PEN', 'PRE', 'PAC', 'SHP', 'CAN']
        if new_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid status'}, status=400)

        # Ensure the producer only updates their own order summaries
        summary = ProducerOrderSummary.objects.get(
            id=summary_id, 
            producer=request.user.producer_profile
        )
        
        summary.status = new_status
        summary.save()
        return JsonResponse({'success': True})
        
    except ProducerOrderSummary.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


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