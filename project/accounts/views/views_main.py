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
from django.utils import timezone
from django.db.models import Prefetch, Q
from django.views.decorators.csrf import csrf_exempt

# ---------------------------------------
# Django Models
# ---------------------------------------
from accounts.models import User
from orders.models import (
    Order,
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
from django.core.cache import cache
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

from orders.services.producer_order_status import (
    ProducerOrderStatusError,
    get_allowed_next_statuses,
    update_producer_order_status,
)
from orders.services.producer_order_cancellation import (
    ProducerOrderCancellationError,
    cancel_producer_order_as_producer,
)

from orders.services.producer_item_cancellation import (
    ProducerItemCancellationError,
    cancel_producer_order_item_as_producer,
)

from decimal import Decimal, ROUND_HALF_UP

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


def login_view(request):
    return render(request, "accounts/login.html")


# ---------------------------------------
# Firebase Autheciation function
# ---------------------------------------
@csrf_exempt
def check_email_exists(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = json.loads(request.body)
    email = data.get("email", "").strip()

    if not email:
        return JsonResponse({"exists": False})

    exists = User.objects.filter(email=email).exists()

    return JsonResponse({"exists": exists})


def firebase_auth_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = json.loads(request.body)
    token = data.get("token")

    # Rate limiting
    ip = request.META.get("REMOTE_ADDR", "")
    cache_key = f"login_attempts:{ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= 10:
        return JsonResponse(
            {"error": "Too many login attempts. Please try again later."},
            status=429,
        )

    cache.set(cache_key, attempts + 1, timeout=300)
    try:
        decoded = firebase_auth.verify_id_token(token)
        email = decoded.get("email")

        user, created = User.objects.get_or_create(email=email)

        # Check if user is active
        if not user.is_active:
            return JsonResponse(
                {"error": "Your account is deactivated. Please contact support."},
                status=403,
            )

        # Django session login
        login(request, user)
        remember = data.get("remember", False)

        if remember:
            request.session.set_expiry(60 * 60 * 24 * 1)  # 1 day
        else:
            request.session.set_expiry(60 * 60 * 0.5)  # browser close
        # -----------------------------
        # Generate JWT tokens
        # -----------------------------
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        request.session["jwt_access"] = access_token
        request.session["jwt_refresh"] = str(refresh)

        login_time = timezone.now()
        request.session["login_time"] = login_time.isoformat()

        expiry_timestamp = request.session.get_expiry_date()
        request.session["expiry_time"] = expiry_timestamp.isoformat()

        # -----------------------------
        # Return redirect + tokens
        # -----------------------------
        response = {
            "access": access_token,
            "refresh": str(refresh),
        }

        if user.role == "ADMIN":
            response["redirect"] = "/dashboard/"
        elif user.role == "PRODUCER":
            response["redirect"] = "/producer/"
        else:
            response["redirect"] = "/"

        return JsonResponse(response)

    except Exception:
        return JsonResponse(
            {"error": "Invalid login credentials."},
            status=400,
        )


# ---------------------------------------
# Profile URL
# ---------------------------------------
@login_required
def profile(request):
    return render(request, "accounts/profile.html")


# ---------------------------------------
# Producer Dashboard URL
# ---------------------------------------
PRODUCER_PAYOUT_RATE = Decimal("0.95")


def _dashboard_money(amount):
    return Decimal(amount or 0).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _dashboard_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _quantity_label(quantity):
    quantity = _dashboard_int(quantity)
    return "1 unit" if quantity == 1 else f"{quantity} units"


def attach_producer_dashboard_item_values(summary):
    items = list(getattr(summary.order, "my_items", []))

    active_items = []
    cancelled_items = []

    original_subtotal = Decimal("0.00")
    active_subtotal = Decimal("0.00")
    cancelled_subtotal = Decimal("0.00")

    total_quantity = 0
    active_quantity_total = 0
    cancelled_quantity_total = 0

    active_line_count = 0
    cancelled_line_count = 0

    summary_is_cancelled = summary.status == ProducerOrderSummary.Status.CANCELLED

    for item in items:
        quantity = max(_dashboard_int(getattr(item, "quantity", 0)), 0)
        stored_cancelled_quantity = max(
            _dashboard_int(getattr(item, "cancelled_quantity", 0)),
            0,
        )

        unit_price = Decimal(getattr(item, "final_unit_price", 0) or 0)

        original_subtotal += unit_price * Decimal(quantity)
        total_quantity += quantity

        # Defensive display rule:
        # If the producer section or the item is cancelled, show the whole item
        # quantity as cancelled even if older data has cancelled_quantity = 0.
        if summary_is_cancelled or item.status == OrderItem.Status.CANCELLED:
            dashboard_cancelled_quantity = quantity
        else:
            dashboard_cancelled_quantity = min(stored_cancelled_quantity, quantity)

        dashboard_active_quantity = max(quantity - dashboard_cancelled_quantity, 0)

        item.dashboard_active_quantity = dashboard_active_quantity
        item.dashboard_cancelled_quantity = dashboard_cancelled_quantity

        item.dashboard_is_cancelled = dashboard_active_quantity <= 0
        item.dashboard_is_partially_cancelled = (
            dashboard_cancelled_quantity > 0 and dashboard_active_quantity > 0
        )

        if item.dashboard_is_cancelled:
            item.dashboard_quantity_summary = (
                f"{_quantity_label(dashboard_cancelled_quantity)} cancelled"
            )
        elif item.dashboard_is_partially_cancelled:
            item.dashboard_quantity_summary = (
                f"{_quantity_label(dashboard_active_quantity)} active, "
                f"{_quantity_label(dashboard_cancelled_quantity)} cancelled"
            )
        else:
            item.dashboard_quantity_summary = (
                f"{_quantity_label(dashboard_active_quantity)} active"
            )

        if dashboard_active_quantity > 0:
            active_items.append(item)
            active_line_count += 1
            active_quantity_total += dashboard_active_quantity
            active_subtotal += unit_price * Decimal(dashboard_active_quantity)

        if dashboard_cancelled_quantity > 0:
            cancelled_items.append(item)
            cancelled_line_count += 1
            cancelled_quantity_total += dashboard_cancelled_quantity
            cancelled_subtotal += unit_price * Decimal(dashboard_cancelled_quantity)

    dashboard_is_fully_cancelled = (
        summary_is_cancelled
        or (total_quantity > 0 and active_quantity_total == 0)
    )

    summary.active_items = active_items
    summary.cancelled_items = cancelled_items

    summary.active_item_count = active_line_count
    summary.cancelled_item_count = cancelled_line_count
    summary.total_item_count = len(items)

    summary.active_quantity_total = active_quantity_total
    summary.cancelled_quantity_total = cancelled_quantity_total
    summary.total_quantity = total_quantity

    summary.has_cancelled_items = cancelled_quantity_total > 0
    summary.dashboard_is_fully_cancelled = dashboard_is_fully_cancelled

    summary.original_subtotal = _dashboard_money(original_subtotal)
    summary.cancelled_subtotal = _dashboard_money(cancelled_subtotal)

    if dashboard_is_fully_cancelled:
        summary.display_subtotal = Decimal("0.00")
        summary.display_payout_amount = Decimal("0.00")
        summary.dashboard_item_status_label = "All items cancelled"

        if cancelled_quantity_total > 0:
            summary.dashboard_item_status_help = (
                f"{_quantity_label(cancelled_quantity_total)} cancelled"
            )
        else:
            summary.dashboard_item_status_help = "No active items"

        summary.dashboard_value_help = "Original value before cancellation"
        summary.dashboard_payout_help = "No payout due"
    else:
        summary.display_subtotal = _dashboard_money(active_subtotal)
        summary.display_payout_amount = _dashboard_money(
            active_subtotal * PRODUCER_PAYOUT_RATE
        )

        summary.dashboard_item_status_label = (
            f"{_quantity_label(active_quantity_total)} active"
        )

        if cancelled_quantity_total > 0:
            summary.dashboard_item_status_help = (
                f"{_quantity_label(cancelled_quantity_total)} cancelled"
            )
        else:
            summary.dashboard_item_status_help = "No cancelled items"

        summary.dashboard_value_help = "Current value after cancellations"
        summary.dashboard_payout_help = "Current producer payout"


@login_required
def producer_dashboard(request):
    if request.user.role != "PRODUCER" or not hasattr(request.user, "producer_profile"):
        return redirect("home:index")

    producer = request.user.producer_profile

    order_search = (request.GET.get("order_id") or "").strip()
    order_search = order_search.lstrip("#").strip()

    # 1. Fetch physical orders
    summaries = (
        ProducerOrderSummary.objects.filter(producer=producer)
        .select_related(
            "order",
            "order__user",
            "order__delivery_address",
            "order__recurring_order",
        )
        .prefetch_related(
            Prefetch(
                "order__items",
                queryset=OrderItem.objects.filter(producer=producer).select_related(
                    "product"
                ),
                to_attr="my_items",
            )
        )
    )

    if order_search:
        order_filter = Q(order__unique_reference__icontains=order_search)

        if order_search.isdigit():
            order_filter |= Q(order__id=int(order_search))

        summaries = summaries.filter(order_filter)

    summaries = summaries.order_by("delivery_date")

    for summary in summaries:
        attach_producer_dashboard_item_values(summary)

        summary.allowed_next_statuses_json = json.dumps(
            [
                {
                    "value": status,
                    "label": ProducerOrderSummary.Status(status).label,
                }
                for status in get_allowed_next_statuses(summary)
            ]
        )

    # 2. Fetch Recurring Templates
    recurring_qs = (
        RecurringOrder.objects.filter(
            items__product__producer=producer,
        )
        .distinct()
        .select_related("user", "delivery_address")
    )

    all_subscriptions = []

    for ro in recurring_qs:
        ro_items = ro.items.filter(product__producer=producer).select_related("product")

        if ro_items.exists():
            all_subscriptions.append(
                {
                    "id": ro.id,
                    "status": ro.status,
                    "status_display": ro.get_status_display(),
                    "customer_name": ro.user.name if ro.user else "Unknown",
                    "customer_email": ro.user.email if ro.user else "",
                    "customer_phone": ro.user.phone if ro.user else "",
                    "delivery_address": ro.delivery_address,
                    "special_instructions": ro.special_instructions,
                    "recurrence_pattern": (
                        ro.get_recurrence_pattern_display()
                        if ro.recurrence_pattern
                        else "Weekly"
                    ),
                    "recurrence_day": (
                        ro.get_recurrence_day_display()
                        if ro.recurrence_day
                        else "Not Set"
                    ),
                    "delivery_day": (
                        ro.get_delivery_day_display() if ro.delivery_day else "Not Set"
                    ),
                    "items": ro_items,
                    "created_at": ro.created_at,
                }
            )

    # 3. Fetch Status History
    history_records = ProducerOrderStatusHistory.objects.filter(
        producer_order_summary__producer=producer
    ).select_related(
        "producer_order_summary__order"
    ).order_by("-changed_at")

    context = {
        "summaries": summaries,
        "all_subscriptions": all_subscriptions,
        "history_records": history_records,
        "order_search": order_search,
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
    statuses = set(summaries.values_list("status", flat=True))

    if not statuses:
        return

    # All cancelled → order cancelled
    if statuses == {"CAN"}:
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return

    # Ignore cancelled summaries for progression logic
    active = statuses - {"CAN"}

    # All remaining are completed → order completed
    if active == {"COM"}:
        order.status = Order.Status.COMPLETED
        order.save(update_fields=["status"])
        return

    # Priority order (least progressed first)
    PROGRESSION = ["PEN", "PRE", "PAC", "SHP", "COM"]

    # Find the least-progressed active summary
    least = None
    for code in PROGRESSION:
        if code in active:
            least = code
            break

    # Map producer summary status → Order status
    if least == "PEN":
        new_order_status = Order.Status.PENDING
    elif least == "PRE":
        new_order_status = Order.Status.IN_PROGRESS
    elif least == "PAC":
        new_order_status = Order.Status.PACKAGED
    elif least == "SHP":
        new_order_status = Order.Status.COMPLETED
    elif least == "COM":
        new_order_status = Order.Status.COMPLETED
    else:
        return  # unknown, don't touch

    if order.status != new_order_status:
        order.status = new_order_status
        order.save(update_fields=["status"])


@login_required
@require_POST
def cancel_producer_order(request, summary_id):
    if request.user.role != "PRODUCER" or not hasattr(request.user, "producer_profile"):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body or "{}")
        reason = data.get("reason", "")

        result = cancel_producer_order_as_producer(
            summary_id=summary_id,
            producer=request.user.producer_profile,
            cancelled_by=request.user,
            reason=reason,
        )

        summary = result["summary"]
        order = result["order"]

        return JsonResponse(
            {
                "success": True,
                "message": "Producer order cancelled successfully.",
                "producer_status": summary.status,
                "producer_status_display": summary.get_status_display(),
                "order_status": order.status,
                "order_status_display": order.get_status_display(),
                "refund": result.get("refund"),
                "allowed_next_statuses": [],
            }
        )

    except ProducerOrderSummary.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    except ProducerOrderCancellationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

@login_required
@require_POST
def cancel_producer_order_item(request, item_id):
    if request.user.role != "PRODUCER" or not hasattr(request.user, "producer_profile"):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body or "{}")
        reason = data.get("reason", "")
        quantity_to_cancel = data.get("quantity_to_cancel")

        result = cancel_producer_order_item_as_producer(
            order_item_id=item_id,
            producer=request.user.producer_profile,
            cancelled_by=request.user,
            quantity_to_cancel=quantity_to_cancel,
            reason=reason,
        )

        item = result["item"]
        summary = result["producer_summary"]
        order = result["order"]

        return JsonResponse(
            {
                "success": True,
                "message": "Producer order item cancelled successfully.",
                "item": {
                    "id": item.id,
                    "status": item.status,
                    "status_display": item.get_status_display(),
                    "quantity": item.quantity,
                    "cancelled_quantity": item.cancelled_quantity,
                    "active_quantity": item.active_quantity,
                },
                "producer_status": summary.status,
                "producer_status_display": summary.get_status_display(),
                "order_status": order.status,
                "order_status_display": order.get_status_display(),
                "refund": result.get("refund"),
                "cancelled_quantity": result.get("cancelled_quantity"),
            }
        )

    except OrderItem.DoesNotExist:
        return JsonResponse({"error": "Order item not found"}, status=404)

    except ProducerItemCancellationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

@login_required
@require_POST
def update_order_status(request, summary_id):
    if request.user.role != "PRODUCER" or not hasattr(request.user, "producer_profile"):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body)
        new_status = data.get("status")
        # Extract note from request, use default if empty or not provided
        custom_note = data.get("note", "").strip()
        final_note = custom_note if custom_note else "Status updated via Producer Dashboard"

        valid_statuses = [
            ProducerOrderSummary.Status.PENDING,
            ProducerOrderSummary.Status.PREPARING,
            ProducerOrderSummary.Status.PACKAGED,
            ProducerOrderSummary.Status.READY_FOR_COLLECTION,
            ProducerOrderSummary.Status.SHIPPED,
            ProducerOrderSummary.Status.COMPLETED,
        ]

        if new_status not in valid_statuses:
            return JsonResponse({"error": "Invalid status"}, status=400)

        result = update_producer_order_status(
            summary_id=summary_id,
            producer=request.user.producer_profile,
            updated_by=request.user,
            new_status=new_status,
            note=final_note,
        )

        summary = result["summary"]
        order = result["order"]

        return JsonResponse(
            {
                "success": True,
                "changed": result["changed"],
                "producer_status": summary.status,
                "producer_status_display": summary.get_status_display(),
                "order_status": order.status,
                "order_status_display": order.get_status_display(),
                "allowed_next_statuses": [
                    {
                        "value": status,
                        "label": ProducerOrderSummary.Status(status).label,
                    }
                    for status in get_allowed_next_statuses(summary)
                ],
            }
        )

    except ProducerOrderSummary.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    except ProducerOrderStatusError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_POST
def cancel_subscription(request, sub_id):
    """
    Cancels the recurring subscription.
    Keeps the nearest physical order summary, but cancels all future ones.
    """
    if request.user.role != "PRODUCER":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        producer = request.user.producer_profile
        sub = RecurringOrder.objects.get(id=sub_id)

        # Security: Ensure this producer owns items in this subscription
        if not sub.items.filter(product__producer=producer).exists():
            return JsonResponse({"error": "Unauthorized"}, status=403)

        # 1. Cancel the subscription template
        sub.status = RecurringOrder.Status.CANCELLED
        sub.save(update_fields=["status"])

        # 2. Find all generated order summaries for this subscription & producer, ordered by date
        summaries = list(
            ProducerOrderSummary.objects.filter(
                order__recurring_order=sub, producer=producer
            ).order_by("delivery_date")
        )

        # Keep the first (nearest) one active, cancel the rest
        if len(summaries) > 1:
            for summary in summaries[1:]:
                # Only cancel if it's not already shipped or packaged
                if summary.status not in ["CAN", "SHP", "PAC"]:
                    old_status = summary.status
                    summary.status = "CAN"
                    summary.save(update_fields=["status"])

                    # Log the cancellation history
                    ProducerOrderStatusHistory.objects.create(
                        producer_order_summary=summary,
                        old_status=old_status,
                        new_status="CAN",
                        updated_by=request.user,
                        note="Automatically cancelled because the parent subscription was cancelled.",
                    )

                    # Sync the parent order status from all its summaries
                    _sync_order_status(summary.order)

        return JsonResponse({"success": True})

    except RecurringOrder.DoesNotExist:
        return JsonResponse({"error": "Subscription not found"}, status=404)


@login_required
@require_POST
def toggle_subscription(request, sub_id):
    """
    Toggles a recurring subscription between ACTIVE and PAUSED.
    """
    if request.user.role != "PRODUCER":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        producer = request.user.producer_profile
        sub = RecurringOrder.objects.get(id=sub_id)

        # Security: Ensure this producer owns items in this subscription
        if not sub.items.filter(product__producer=producer).exists():
            return JsonResponse({"error": "Unauthorized"}, status=403)

        if sub.status == RecurringOrder.Status.CANCELLED:
            return JsonResponse(
                {"error": "Cannot toggle a cancelled subscription"}, status=400
            )

        if sub.status == RecurringOrder.Status.ACTIVE:
            sub.status = RecurringOrder.Status.PAUSED
        else:
            sub.status = RecurringOrder.Status.ACTIVE

        sub.save(update_fields=["status"])

        return JsonResponse(
            {
                "success": True,
                "new_status": sub.status,
                "new_status_display": sub.get_status_display(),
            }
        )

    except RecurringOrder.DoesNotExist:
        return JsonResponse({"error": "Subscription not found"}, status=404)


# ---------------------------------------
# API Endpoint URL
# ---------------------------------------
class UnifiedRegistrationView(APIView):
    def post(self, request):
        role = request.data.get("role", "").lower()

        if role not in ["customer", "producer"]:
            return Response(
                {"role": ["Invalid registration role."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role == "producer":
            serializer = ProducerRegistrationSerializer(data=request.data)
        else:
            serializer = CustomerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": f"{role.capitalize()} registered successfully"},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
