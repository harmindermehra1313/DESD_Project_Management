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
from orders.models import ProducerOrderSummary, OrderItem, RecurringOrder, ProducerOrderStatusHistory
from django.db.models import Prefetch
from django.contrib.auth import logout
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
import datetime
from django.utils import timezone
from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer

def register(request):
    return render(request, "accounts/register.html")

def logout_view(request):
    logout(request)
    return redirect("home:index")

# New Login function to generate jwt tokens
# def login_view(request):
#     if request.method == "POST":
#         email = request.POST.get("email", "").strip().lower()
#         password = request.POST.get("password")
#         remember = request.POST.get("remember")

#         user = authenticate(request, username=email, password=password)

#         if user is not None:
#             login(request, user)

#             # Session expiry
#             if not remember:
#                 request.session.set_expiry(0)
#             else:
#                 request.session.set_expiry(60 * 60 * 24 * 1)

#             # Generate JWT tokens
#             refresh = RefreshToken.for_user(user)
#             access_token = str(refresh.access_token)

#             # Store tokens in session (optional)
#             request.session["jwt_access"] = access_token
#             request.session["jwt_refresh"] = str(refresh)
            
#             from django.utils import timezone

#             # Record login time (timezone-aware)
#             login_time = timezone.now()
#             request.session["login_time"] = login_time.isoformat()

#             # Get session expiry (already timezone-aware)
#             expiry_timestamp = request.session.get_expiry_date()
#             request.session["expiry_time"] = expiry_timestamp.isoformat()

#             print("LOGIN TIME:", login_time)
#             print("SESSION EXPIRES AT:", expiry_timestamp)

#             # Calculate remaining time safely
#             remaining = expiry_timestamp - login_time
#             print("TIME UNTIL LOGOUT:", remaining)

#             # Debug print (optional)
#             print("JWT ACCESS:", access_token)
#             print("USER:", request.user)
#             print("ROLE:", request.user.role)
#             print("AUTH:", request.user.is_authenticated)

#             # Redirect based on role
#             if user.role == "ADMIN":
#                 return redirect("home:dashboard")
#             elif user.role =='PRODUCER':
#                 return redirect("home:producer")
#             else:
#                 return redirect("home:index")

#         else:
#             messages.error(request, "Invalid email or password.")

#     return render(request, "accounts/login.html")

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        remember = request.POST.get("remember")

        # STEP 1 — Check if user exists BEFORE authenticate()
        try:
            user_obj = User.objects.get(email=email)
            if not user_obj.is_active:
                messages.error(request, "Your account has been deactivated. Please contact support.")
                return render(request, "accounts/login.html")
        except User.DoesNotExist:
            user_obj = None

        # STEP 2 — Authenticate normally
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


            request.session["jwt_access"] = access_token
            request.session["jwt_refresh"] = str(refresh)

            login_time = timezone.now()
            request.session["login_time"] = login_time.isoformat()

            expiry_timestamp = request.session.get_expiry_date()
            
            request.session["expiry_time"] = expiry_timestamp.isoformat()

            # Redirect based on role
            if user.role == "ADMIN":
                return redirect("home:dashboard")
            elif user.role == "PRODUCER":
                return redirect("home:producer")
            else:
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
    
    # 1. Fetch physical orders
    summaries = ProducerOrderSummary.objects.filter(
        producer=producer
    ).select_related(
        'order', 
        'order__user', 
        'order__delivery_address',
        'order__recurring_order' # Fetch recurring order relationship
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

    # 2. Fetch Active Recurring Templates to give producers advance notice
    recurring_qs = RecurringOrder.objects.filter(
        items__product__producer=producer,
        status='ACT'
    ).distinct().select_related('user', 'delivery_address')

    active_subscriptions = []
    for ro in recurring_qs:
        # Get only the items relevant to THIS producer
        ro_items = ro.items.filter(product__producer=producer).select_related('product')
        if ro_items.exists():
            active_subscriptions.append({
                'id': ro.id,
                'customer_name': ro.user.name if ro.user else "Unknown",
                'customer_email': ro.user.email if ro.user else "",
                'customer_phone': ro.user.phone if ro.user else "",
                'delivery_address': ro.delivery_address,
                'special_instructions': ro.special_instructions,
                'recurrence_day': ro.get_recurrence_day_display() if ro.recurrence_day else "Not Set",
                'delivery_day': ro.get_delivery_day_display() if ro.delivery_day else "Not Set",
                'items': ro_items,
                'created_at': ro.created_at
            })

    context = {
        'summaries': summaries,
        'active_subscriptions': active_subscriptions,
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
        
        # 1. Capture the old status before updating
        old_status = summary.status
        
        # 2. Only update and log if the status actually changed
        if old_status != new_status:
            summary.status = new_status
            summary.save(update_fields=['status'])

            # 3. Create the history record
            ProducerOrderStatusHistory.objects.create(
                producer_order_summary=summary,
                old_status=old_status,
                new_status=new_status,
                updated_by=request.user,
                note=f"Status updated via Producer Dashboard"
            )

        return JsonResponse({'success': True})
        
    except ProducerOrderSummary.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@login_required
@require_POST
def cancel_subscription(request, sub_id):
    """
    Cancels the recurring subscription. 
    Keeps the nearest physical order summary, but cancels all future ones.
    """
    if request.user.role != 'PRODUCER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        producer = request.user.producer_profile
        sub = RecurringOrder.objects.get(id=sub_id)

        # Security: Ensure this producer owns items in this subscription
        if not sub.items.filter(product__producer=producer).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        # 1. Cancel the subscription template
        sub.status = RecurringOrder.Status.CANCELLED
        sub.save(update_fields=['status'])

        # 2. Find all generated order summaries for this subscription & producer, ordered by date
        summaries = list(ProducerOrderSummary.objects.filter(
            order__recurring_order=sub,
            producer=producer
        ).order_by('delivery_date'))

        # Keep the first (nearest) one active, cancel the rest
        if len(summaries) > 1:
            for summary in summaries[1:]:
                # Only cancel if it's not already shipped or packaged
                if summary.status not in ['CAN', 'SHP', 'PAC']: 
                    old_status = summary.status
                    summary.status = 'CAN'
                    summary.save(update_fields=['status'])
                    
                    # Log the cancellation history
                    ProducerOrderStatusHistory.objects.create(
                        producer_order_summary=summary,
                        old_status=old_status,
                        new_status='CAN',
                        updated_by=request.user,
                        note="Automatically cancelled because the parent subscription was cancelled."
                    )
                    
                    # Also update the main parent order status
                    order = summary.order
                    order.status = 'CAN'
                    order.save(update_fields=['status'])

        return JsonResponse({'success': True})

    except RecurringOrder.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)


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