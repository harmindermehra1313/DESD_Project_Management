# ---------------------------------------
# Standard Library
# ---------------------------------------
import json
import datetime

# ---------------------------------------
# Django Core
# ---------------------------------------
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import Order, timezone
from django.db.models import Prefetch

# ---------------------------------------
# Django Models
# ---------------------------------------
from accounts.models import User
from orders.models import (
    ProducerOrderSummary,
    OrderItem,
    RecurringOrder,
    ProducerOrderStatusHistory,
)

# ---------------------------------------
# Django REST Framework
# ---------------------------------------
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# ---------------------------------------
# JWT / Authentication
# ---------------------------------------
from rest_framework_simplejwt.tokens import RefreshToken

# ---------------------------------------
# Firebase
# ---------------------------------------
from firebase_admin import auth as firebase_auth

# ---------------------------------------
# Serializers
# ---------------------------------------
from accounts.serializers.registration_customer import CustomerRegistrationSerializer
from accounts.serializers.registration_producer import ProducerRegistrationSerializer


# ---------------------------------------
# Register URL
# ---------------------------------------
def register(request):
    return render(request, "accounts/register.html")

# ---------------------------------------
# Logout URL
# ---------------------------------------
def logout_view(request):
    logout(request)
    return redirect("home:index")

# New Login function to generate jwt tokens

# def login_view(request):
#     if request.method == "POST":
#         email = request.POST.get("email", "").strip().lower()
#         password = request.POST.get("password")
#         remember = request.POST.get("remember")

#         # STEP 1 — Check if user exists BEFORE authenticate()
#         try:
#             user_obj = User.objects.get(email=email)
#             if not user_obj.is_active:
#                 messages.error(request, "Your account has been deactivated. Please contact support.")
#                 return render(request, "accounts/login.html")
#         except User.DoesNotExist:
#             user_obj = None

#         # STEP 2 — Authenticate normally
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


#             request.session["jwt_access"] = access_token
#             request.session["jwt_refresh"] = str(refresh)

#             login_time = timezone.now()
#             request.session["login_time"] = login_time.isoformat()

#             expiry_timestamp = request.session.get_expiry_date()
            
#             request.session["expiry_time"] = expiry_timestamp.isoformat()

#             # Redirect based on role
#             if user.role == "ADMIN":
#                 return redirect("home:dashboard")
#             elif user.role == "PRODUCER":
#                 return redirect("home:producer")
#             else:
#                 return redirect("home:index")

#         else:
#             messages.error(request, "Invalid email or password.")

#     return render(request, "accounts/login.html")

def login_view(request):
    return render(request, "accounts/login.html")

# ---------------------------------------
# Firebase Autheciation function
# ---------------------------------------
def firebase_auth_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = json.loads(request.body)
    token = data.get("token")

    try:
        decoded = firebase_auth.verify_id_token(token)
        email = decoded.get("email")

        user, created = User.objects.get_or_create(email=email)

        # Check if user is active
        if not user.is_active:
            print("DEBUG: User is deactivated")   # <-- This will show in your terminal
            return JsonResponse({"error": "Your account is deactivated. Please contact support."}, status=403)

        login(request, user)

        if user.role == "ADMIN":
            return JsonResponse({"redirect": "/dashboard/"})
        elif user.role == "PRODUCER":
            return JsonResponse({"redirect": "/producer/"})
        else:
            return JsonResponse({"redirect": "/"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

# ---------------------------------------
# Profile URL
# ---------------------------------------
@login_required
def profile(request):
    return render(request, "accounts/profile.html")

# ---------------------------------------
# Producer URL
# ---------------------------------------
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

    # 2. Fetch Recurring Templates (all statuses, so the front-end filter works)
    recurring_qs = RecurringOrder.objects.filter(
        items__product__producer=producer,
    ).distinct().select_related('user', 'delivery_address')

    all_subscriptions = []
    for ro in recurring_qs:
        # Get only the items relevant to THIS producer
        ro_items = ro.items.filter(product__producer=producer).select_related('product')
        if ro_items.exists():
            all_subscriptions.append({
                'id': ro.id,
                'status': ro.status,
                'status_display': ro.get_status_display(),
                'customer_name': ro.user.name if ro.user else "Unknown",
                'customer_email': ro.user.email if ro.user else "",
                'customer_phone': ro.user.phone if ro.user else "",
                'delivery_address': ro.delivery_address,
                'special_instructions': ro.special_instructions,
                'recurrence_pattern': ro.get_recurrence_pattern_display() if ro.recurrence_pattern else "Weekly",
                'recurrence_day': ro.get_recurrence_day_display() if ro.recurrence_day else "Not Set",
                'delivery_day': ro.get_delivery_day_display() if ro.delivery_day else "Not Set",
                'items': ro_items,
                'created_at': ro.created_at
            })

    context = {
        'summaries': summaries,
        'all_subscriptions': all_subscriptions,
    }
    
    return render(request, "accounts/producer_dashboard.html", context)


def _sync_order_status(order):
    """
    Derive the parent Order.status from the statuses of all its
    ProducerOrderSummary rows.

    Mapping (ProducerOrderSummary → Order):
        PEN  (Pending)   → PEN  (Pending)
        PRE  (Preparing) → IP   (In Progress)
        PAC  (Packaged)  → OFD  (Packaged)
        SHP  (Shipped)   → CMP  (Completed)
        COM  (Completed) → CMP  (Completed)
        CAN  (Cancelled) → CAN  (Cancelled)

    For multi-producer orders the "least progressed" summary wins,
    except: if every summary is cancelled the order is cancelled,
    and the order is only completed when every summary is completed
    (or cancelled).
    """
    summaries = order.producer_summaries.all()
    statuses = set(summaries.values_list('status', flat=True))

    if not statuses:
        return

    # All cancelled → order cancelled
    if statuses == {'CAN'}:
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])
        return

    # Ignore cancelled summaries for progression logic
    active = statuses - {'CAN'}

    # All remaining are completed → order completed
    if active == {'COM'}:
        order.status = Order.Status.COMPLETED
        order.save(update_fields=['status'])
        return

    # Priority order (least progressed first)
    PROGRESSION = ['PEN', 'PRE', 'PAC', 'SHP', 'COM']

    # Find the least-progressed active summary
    least = None
    for code in PROGRESSION:
        if code in active:
            least = code
            break

    # Map producer summary status → Order status
    if least == 'PEN':
        new_order_status = Order.Status.PENDING
    elif least == 'PRE':
        new_order_status = Order.Status.IN_PROGRESS
    elif least == 'PAC':
        new_order_status = Order.Status.PACKAGED
    elif least == 'SHP':
        new_order_status = Order.Status.COMPLETED
    elif least == 'COM':
        new_order_status = Order.Status.COMPLETED
    else:
        return  # unknown, don't touch

    if order.status != new_order_status:
        order.status = new_order_status
        order.save(update_fields=['status'])


@login_required
@require_POST
def update_order_status(request, summary_id):
    if request.user.role != 'PRODUCER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        valid_statuses = ['PEN', 'PRE', 'PAC', 'SHP', 'CAN', 'COM']
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

            # 4. Directly update the parent Order status
            SUMMARY_TO_ORDER = {
                'PEN': Order.Status.PENDING,        # PEN → PEN
                'PRE': Order.Status.IN_PROGRESS,    # PRE → IP
                'PAC': Order.Status.PACKAGED,       # PAC → OFD
                'SHP': Order.Status.COMPLETED,      # SHP → CMP
                'COM': Order.Status.COMPLETED,      # COM → CMP
                'CAN': Order.Status.CANCELLED,      # CAN → CAN
            }
            mapped_status = SUMMARY_TO_ORDER.get(new_status)
            if mapped_status and summary.order.status != mapped_status:
                summary.order.status = mapped_status
                summary.order.save(update_fields=['status'])

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
                    
                    # Sync the parent order status from all its summaries
                    _sync_order_status(summary.order)

        return JsonResponse({'success': True})

    except RecurringOrder.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)


@login_required
@require_POST
def toggle_subscription(request, sub_id):
    """
    Toggles a recurring subscription between ACTIVE and PAUSED.
    """
    if request.user.role != 'PRODUCER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        producer = request.user.producer_profile
        sub = RecurringOrder.objects.get(id=sub_id)

        # Security: Ensure this producer owns items in this subscription
        if not sub.items.filter(product__producer=producer).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        if sub.status == RecurringOrder.Status.CANCELLED:
            return JsonResponse({'error': 'Cannot toggle a cancelled subscription'}, status=400)

        if sub.status == RecurringOrder.Status.ACTIVE:
            sub.status = RecurringOrder.Status.PAUSED
        else:
            sub.status = RecurringOrder.Status.ACTIVE

        sub.save(update_fields=['status'])

        return JsonResponse({
            'success': True,
            'new_status': sub.status,
            'new_status_display': sub.get_status_display(),
        })

    except RecurringOrder.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)

# ---------------------------------------
# API Endpoint URL
# ---------------------------------------
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