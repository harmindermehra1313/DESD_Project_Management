# -----------------------------
# Standard Library Imports
# -----------------------------
from datetime import datetime, date
from decimal import Decimal
import csv
import json
from xhtml2pdf import pisa

# -----------------------------
# Django Imports
# -----------------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.template.loader import get_template
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

# -----------------------------
# Project Imports
# -----------------------------
from BRFN.decorators import admin_required
from orders.models import Order, ProducerOrderSummary
from accounts.models import User, Producer, Admin
from products.models import Product
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from products.models import Product
from notifications.models import Notification
from django_q.tasks import async_task
from admin_records.tasks import send_action_required_email, send_rejection_email
from payments.models import Payment, PaymentRefund

from admin_records.models import ModerationLog

COMMISSION_RATE = Decimal("0.05")
PRODUCER_RATE = Decimal("0.95")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _clean_producer_id(raw):
    if raw in ["", "None", None]:
        return None
    return int(raw)


@admin_required
def user_list(request):
    users = User.objects.exclude(role="ADMIN").order_by("-created_at")
    return render(request, "admin_records/user_list.html", {"users": users})

@login_required
@admin_required
@require_POST
def reject_producer(request, producer_id):
    producer = get_object_or_404(Producer, id=producer_id)

    reason = request.POST.get("reason", "Producer registration rejected by admin.")

    producer.is_approved = False
    producer.approved_at = None
    producer.approved_by_admin = None
    producer.save(update_fields=["is_approved", "approved_at", "approved_by_admin"])

    producer.user.is_active = False
    producer.user.deactivation_reason = reason
    producer.user.deactivated_at = timezone.now()
    producer.user.deactivated_by = request.user
    producer.user.save(update_fields=[
        "is_active",
        "deactivation_reason",
        "deactivated_at",
        "deactivated_by",
    ])

    messages.warning(request, f"{producer.farm_name} has been rejected and deactivated.")
    return redirect("admin_records:producer_list")

@admin_required
def producer_list(request):
    producers = Producer.objects.all().order_by("farm_name")
    return render(request, "admin_records/producer_list.html", {"producers": producers})



@login_required
@admin_required
@require_POST
def approve_producer(request, producer_id):
    producer = get_object_or_404(Producer, id=producer_id)

    producer.is_approved = True
    producer.approved_at = timezone.now()
    producer.approved_by_admin = request.user
    producer.save(update_fields=["is_approved", "approved_at", "approved_by_admin"])

    messages.success(request, f"{producer.farm_name} has been approved successfully.")
    return redirect("admin_records:producer_list")

@admin_required
def index(request):
    return render(request, "admin_records/index.html")


def _build_financial_context(request):
    start_date = _parse_date(request.GET.get("start_date"))
    end_date = _parse_date(request.GET.get("end_date"))
    producer_id = _clean_producer_id(request.GET.get("producer"))
    status = request.GET.get("status") or ""

    orders = Order.objects.all().prefetch_related(
    "producer_summaries", "producer_summaries__producer"
    )

    if start_date:
        orders = orders.filter(order_date__date__gte=start_date)

    if end_date:
        orders = orders.filter(order_date__date__lte=end_date)

    if status:
        if status == "CAN":
            orders = orders.filter(
                Q(status=Order.Status.CANCELLED) |
                Q(producer_summaries__status=ProducerOrderSummary.Status.CANCELLED)
            ).distinct()
        else:
            orders = orders.filter(status=status)

    if producer_id:
        orders = orders.filter(producer_summaries__producer_id=producer_id).distinct()

    order_rows = []
    total_order_value = Decimal("0.00")
    total_commission_calc = Decimal("0.00")
    total_commission_recorded = Decimal("0.00")
    total_producer_payout = Decimal("0.00")
    total_refunds = Decimal("0.00")

    for order in orders:

        # Always define this
        order_total = order.final_total_price

        # -----------------------------------------
        # NEW LOGIC: Determine payment + refund info
        # -----------------------------------------
        payment = order.payments.order_by("-created_at").first()

        if payment:
            refunds = PaymentRefund.objects.filter(payment=payment)
            successful_refunds = refunds.filter(status="SUC")
            pending_refunds = refunds.filter(status="PEN")
            refund_total = sum((r.amount for r in successful_refunds), Decimal("0.00"))
        else:
            refunds = PaymentRefund.objects.none()
            successful_refunds = []
            pending_refunds = []
            refund_total = Decimal("0.00")

        refund_total = sum((r.amount for r in successful_refunds), Decimal("0.00"))

        if payment:
            payment_method = payment.payment_method
            payment_status = payment.payment_status
        else:
            payment_method = None
            payment_status = None

        # -----------------------------------------
        # NEW LOGIC: Determine active vs cancelled producers
        # -----------------------------------------
        producer_summaries = order.producer_summaries.all()

        active_summaries = producer_summaries.exclude(status="CAN")
        cancelled_summaries = producer_summaries.filter(status="CAN")

        active_subtotal = sum((ps.subtotal for ps in active_summaries), Decimal("0.00"))
        cancelled_subtotal = sum((ps.subtotal for ps in cancelled_summaries), Decimal("0.00"))

        # -----------------------------------------
        # NEW LOGIC: Commission + payout rules
        # -----------------------------------------

        # CASE 1 — FULL ORDER CANCELLED
        if order.status == Order.Status.CANCELLED:
            commission_calc = Decimal("0.00")
            commission_recorded = Decimal("0.00")
            producer_payout_total = Decimal("0.00")

        # CASE 2 — PARTIAL CANCELLATION
        elif cancelled_summaries.exists():
            commission_calc = (active_subtotal * COMMISSION_RATE).quantize(Decimal("0.01"))
            commission_recorded = commission_calc
            producer_payout_total = (active_subtotal - commission_calc).quantize(Decimal("0.01"))

        # CASE 3 — NORMAL ORDER
        else:
            commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
            commission_recorded = order.total_commission.quantize(Decimal("0.01"))
            producer_payout_total = (order_total - commission_calc).quantize(Decimal("0.01"))

        # Update totals
        # CASE 1 — Cancelled cash order → company never received money
        if order.status == Order.Status.CANCELLED and payment_method == "CSH":
            gross_total_add = Decimal("0.00")

        # CASE 2 — All other orders → include in gross total
        else:
            gross_total_add = order_total

        total_order_value += gross_total_add
        total_commission_calc += commission_calc
        total_commission_recorded += commission_recorded
        total_producer_payout += producer_payout_total
        total_refunds += refund_total

        # -----------------------------------------
        # NEW LOGIC: Build producer breakdown lists
        # -----------------------------------------

        producer_breakdown_active = []
        producer_breakdown_cancelled = []
        
        # ACTIVE PRODUCERS
        for ps in active_summaries:
            active_commission = (ps.subtotal * COMMISSION_RATE).quantize(Decimal("0.01"))
            active_payout = (ps.subtotal - active_commission).quantize(Decimal("0.01"))

            producer_breakdown_active.append({
                "producer_name": ps.producer.farm_name,
                "subtotal": ps.subtotal,
                "commission": active_commission,
                "payout": active_payout,
                "status": "ACTIVE",
            })

        # CANCELLED PRODUCERS
        for ps in cancelled_summaries:
            producer_breakdown_cancelled.append({
                "producer_name": ps.producer.farm_name,
                "subtotal": ps.subtotal,
                "refund": refund_total,
                "status": "CANCELLED",
            })

        order_rows.append(
    {
        "order": order,
        "order_total": order_total,
        "commission_calc": commission_calc,
        "commission_recorded": commission_recorded,
        "producer_payout_total": producer_payout_total,

        # NEW REFUND FIELDS
        "refund_total": refund_total,
        "payment_method": payment_method,
        "payment_status": payment_status,
        "refund_pending": bool(pending_refunds),

        # NEW PRODUCER BREAKDOWN
        "active_producers": producer_breakdown_active,
        "cancelled_producers": producer_breakdown_cancelled,
    }
    )

    net_sales = total_order_value - total_refunds
    producers = Producer.objects.all()

    context = {
        "order_rows": order_rows,
        "total_order_value": total_order_value.quantize(Decimal("0.01")),
        "total_commission_calc": total_commission_calc.quantize(Decimal("0.01")),
        "total_commission_recorded": total_commission_recorded.quantize(Decimal("0.01")),
        "total_producer_payout": total_producer_payout.quantize(Decimal("0.01")),
        "gross_total": total_order_value.quantize(Decimal("0.01")),
        "refund_total": total_refunds.quantize(Decimal("0.01")),
        "net_sales": net_sales.quantize(Decimal("0.01")),
        "producers": producers,
        "selected_producer": producer_id,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
    }
    return context


@admin_required
def financial_reports(request):
    context = _build_financial_context(request)
    return render(request, "admin_records/financial_reports.html", context)


@admin_required
def financial_reports_csv(request):
    start_date = _parse_date(request.GET.get("start_date"))
    end_date = _parse_date(request.GET.get("end_date"))
    producer_id = _clean_producer_id(request.GET.get("producer"))
    status = request.GET.get("status") or ""

    orders = Order.objects.all().prefetch_related(
        "producer_summaries", "producer_summaries__producer"
        )

        # Apply the SAME filters
    if start_date:
        orders = orders.filter(order_date__date__gte=start_date)

    if end_date:
        orders = orders.filter(order_date__date__lte=end_date)

    if status:
        if status == "CAN":
            orders = orders.filter(
                Q(status=Order.Status.CANCELLED) |
                Q(producer_summaries__status=ProducerOrderSummary.Status.CANCELLED)
            ).distinct()
        else:
            orders = orders.filter(status=status)
    if producer_id:
        orders = orders.filter(producer_summaries__producer_id=producer_id).distinct()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="commission_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Order ID",
        "Reference",
        "Date",
        "Status",
        "Order Total",
        "Commission (5% Calculated)",
        "Commission (Recorded)",
        "Producer Payout Total",
        "Refund Total",
        "Refund Status",
        "Payment Method",
        "Active Producers",
        "Cancelled Producers",
    ])


    for order in orders:

        # Rebuild the same logic used in _build_financial_context()

        order_total = order.final_total_price

        payment = order.payments.order_by("-created_at").first()
        refunds = order.payment_refunds.all()
        successful_refunds = refunds.filter(status="SUC")
        pending_refunds = refunds.filter(status="PEN")

        refund_total = sum((r.amount for r in successful_refunds), Decimal("0.00"))
        refund_status = (
            "Pending" if pending_refunds.exists()
            else "Succeeded" if refund_total > 0
            else "N/A"
        )
        payment_method = payment.payment_method if payment else "N/A"

        producer_summaries = order.producer_summaries.all()
        active_summaries = producer_summaries.exclude(status="CAN")
        cancelled_summaries = producer_summaries.filter(status="CAN")

        active_subtotal = sum((ps.subtotal for ps in active_summaries), Decimal("0.00"))

        # Commission + payout logic
        if order.status == Order.Status.CANCELLED:
            commission_calc = Decimal("0.00")
            commission_recorded = Decimal("0.00")
            producer_payout_total = Decimal("0.00")

        elif cancelled_summaries.exists():
            commission_calc = (active_subtotal * COMMISSION_RATE).quantize(Decimal("0.01"))
            commission_recorded = commission_calc
            producer_payout_total = (active_subtotal - commission_calc).quantize(Decimal("0.01"))

        else:
            commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
            commission_recorded = order.total_commission.quantize(Decimal("0.01"))
            producer_payout_total = (order_total - commission_calc).quantize(Decimal("0.01"))

        # Flatten active producers
        active_list = ", ".join(
            f"{ps.producer.farm_name} (£{ps.subtotal} → payout £{(ps.subtotal - (ps.subtotal * COMMISSION_RATE))})"
            for ps in active_summaries
        )

        # Flatten cancelled producers
        cancelled_list = ", ".join(
            f"{ps.producer.farm_name} (cancelled → refund £{ps.subtotal})"
            for ps in cancelled_summaries
        )

        writer.writerow([
            order.id,
            order.unique_reference,
            order.order_date,
            order.get_status_display(),
            order_total,
            commission_calc,
            commission_recorded,
            producer_payout_total,
            refund_total,
            refund_status,
            payment_method,
            active_list,
            cancelled_list,
        ])



    return response


# @admin_required
from django.utils.timezone import now

@admin_required
def financial_reports_pdf(request):
    context = _build_financial_context(request)
    context["generated_at"] = now()  # Add timestamp

    template = get_template("admin_records/financial_report_pdf.html")
    html = template.render(context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="financial_report.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)

    return response


@require_POST
def deactivate_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    data = json.loads(request.body)
    reason = data.get("reason")

    user.is_active = False
    user.deactivation_reason = reason
    user.deactivated_at = timezone.now()
    user.deactivated_by = request.user
    user.save()

    return JsonResponse({"success": True})

@require_POST
def reactivate_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    user.is_active = True
    user.deactivation_reason = None
    user.deactivated_at = None
    user.deactivated_by = None
    user.save()

    return JsonResponse({"success": True})

def global_search(request):
    query = request.GET.get("q", "").strip()

    producers = Producer.objects.filter(
        Q(farm_name__icontains=query) |
        Q(contact_email__icontains=query) |
        Q(contact_phone__icontains=query) |
        Q(user__name__icontains=query)
    )

    users = User.objects.filter(
        Q(name__icontains=query) |
        Q(email__icontains=query)
    )

    orders = Order.objects.filter(
        Q(unique_reference__icontains=query) |
        Q(user__name__icontains=query)
    )

    products = Product.objects.filter(
        Q(name__icontains=query)
    )

    context = {
        "query": query,
        "producers": producers,
        "users": users,
        "orders": orders,
        "products": products,
    }

    return render(request, "admin_records/global_search_results.html", context)

@admin_required
def approval_requests(request):
    pending_products = Product.objects.filter(status=Product.Status.PENDING)

    return render(request, "admin_records/approval_requests.html", {
        "pending_products": pending_products
    })

def base_context(request):
    pending_count = Product.objects.filter(is_approved=False).count()
    return {"pending_count": pending_count}

def approve_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    admin_obj = Admin.objects.get(user=request.user)

    product.status = Product.Status.PUBLISHED
    product.moderated_at = timezone.now()
    product.moderated_by_admin = admin_obj
    product.save()

    return redirect("admin_records:approval_request")


def reject_product(request, product_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."}, status=400)

    product = get_object_or_404(Product, id=product_id)

    try:
        admin_obj = Admin.objects.get(user=request.user)
    except Admin.DoesNotExist:
        return JsonResponse({"success": False, "error": "Admin profile not found."}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    reason = (data.get("reason") or "").strip()
    if not reason:
        return JsonResponse({"success": False, "error": "Rejection reason is required."}, status=400)

    # Update product status
    product.status = Product.Status.REMOVED
    product.moderated_at = timezone.now()
    product.moderated_by_admin = admin_obj
    product.save()

    # Log moderation action
    ModerationLog.objects.create(
        admin=admin_obj,
        producer=product.producer,
        content_type=ModerationLog.ContentType.PRODUCT,
        content=product.id,
        action=ModerationLog.Action.REJECTED,
        reason=reason,
    )

    # -----------------------------
    # SEND REJECTION EMAIL
    # -----------------------------
    producer_user = product.producer.user
    async_task(
        "admin_records.tasks.send_rejection_email",
        product.id,
        reason,
        admin_obj.user.name,
    )


    return JsonResponse({"success": True})



def product_details(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    data = {
        "name": product.name,
        "description": product.description,
        "producer_name": product.producer.user.name,
        "farm_name": product.producer.farm_name,
        "category": product.category.name,
        "submitted_at": product.created_at.strftime("%d %b %Y, %H:%M") if product.created_at else None,
        "updated_at": product.updated_at.strftime("%d %b %Y, %H:%M") if product.updated_at else None,

        "organic_status": product.get_organic_certification_status_display(),
        "availability_status": product.get_availability_status_display(),
        "price": str(product.price),
        "unit": product.get_unit_display(),
        "farm_origin": product.farm_origin,
    }

    return JsonResponse(data)




def action_required(request, product_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)

    data = json.loads(request.body)
    message = data.get("message")

    async_task(
        "admin_records.tasks.send_action_required_email",
        product_id,
        message,
    )

    return JsonResponse({"success": True})



