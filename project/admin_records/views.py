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
# -----------------------------
# Project Imports
# -----------------------------
from BRFN.decorators import admin_required
from orders.models import Order
from accounts.models import User, Producer, Admin
from products.models import Product
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from products.models import Product
from notifications.models import Notification
from django_q.tasks import async_task
from admin_records.tasks import send_action_required_email, send_rejection_email

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
    users = User.objects.all().order_by("-created_at")
    return render(request, "admin_records/user_list.html", {"users": users})


@admin_required
def producer_list(request):
    producers = Producer.objects.all().order_by("farm_name")
    return render(request, "admin_records/producer_list.html", {"producers": producers})


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
        orders = orders.filter(status=status)

    if producer_id:
        orders = orders.filter(producer_summaries__producer_id=producer_id).distinct()

    order_rows = []
    total_order_value = Decimal("0.00")
    total_commission_calc = Decimal("0.00")
    total_commission_recorded = Decimal("0.00")
    total_producer_payout = Decimal("0.00")

    for order in orders:
        order_total = order.final_total_price
        commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
        commission_recorded = order.total_commission.quantize(Decimal("0.01"))
        producer_payout_total = (order_total - commission_calc).quantize(Decimal("0.01"))

        total_order_value += order_total
        total_commission_calc += commission_calc
        total_commission_recorded += commission_recorded
        total_producer_payout += producer_payout_total

        producer_summaries = order.producer_summaries.all()
        if producer_id:
            producer_summaries = producer_summaries.filter(producer_id=producer_id)

        producer_breakdown = [
            {
                "producer_name": ps.producer.farm_name,
                "subtotal": ps.subtotal,
                "commission_total": ps.commission_total,
                "payout_amount": ps.payout_amount,
            }
            for ps in producer_summaries
        ]

        order_rows.append(
            {
                "order": order,
                "order_total": order_total,
                "commission_calc": commission_calc,
                "commission_recorded": commission_recorded,
                "producer_payout_total": producer_payout_total,
                "producer_breakdown": producer_breakdown,
            }
        )

    today = date.today()
    ytd_orders = Order.objects.filter(order_date__year=today.year)
    ytd_total = (
        ytd_orders.aggregate(s=Sum("final_total_price"))["s"] or Decimal("0.00")
    )
    ytd_commission_calc = (ytd_total * COMMISSION_RATE).quantize(Decimal("0.01"))

    producers = Producer.objects.all()

    context = {
        "order_rows": order_rows,
        "total_order_value": total_order_value.quantize(Decimal("0.01")),
        "total_commission_calc": total_commission_calc.quantize(Decimal("0.01")),
        "total_commission_recorded": total_commission_recorded.quantize(Decimal("0.01")),
        "total_producer_payout": total_producer_payout.quantize(Decimal("0.01")),
        "ytd_total": ytd_total.quantize(Decimal("0.01")),
        "ytd_commission_calc": ytd_commission_calc,
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
        orders = orders.filter(status=status)

    if producer_id:
        orders = orders.filter(producer_summaries__producer_id=producer_id).distinct()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="commission_report.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Order ID",
            "Reference",
            "Date",
            "Status",
            "Order Total",
            "Commission (5%)",
            "Commission Recorded",
            "Producer",
            "Subtotal",
            "Producer Commission",
            "Producer Payout",
        ]
    )

    for order in orders:
        order_total = order.final_total_price
        commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
        commission_recorded = order.total_commission.quantize(Decimal("0.01"))

        producer_summaries = order.producer_summaries.all()
        if producer_id:
            producer_summaries = producer_summaries.filter(producer_id=producer_id)

        if not producer_summaries.exists():
            writer.writerow(
                [
                    order.id,
                    order.unique_reference,
                    order.order_date,
                    order.status,
                    order_total,
                    commission_calc,
                    commission_recorded,
                    "",
                    "",
                    "",
                    "",
                ]
            )
        else:
            for ps in producer_summaries:
                writer.writerow(
                    [
                        order.id,
                        order.unique_reference,
                        order.order_date,
                        order.status,
                        order_total,
                        commission_calc,
                        commission_recorded,
                        ps.producer.farm_name,
                        ps.subtotal,
                        ps.commission_total,
                        ps.payout_amount,
                    ]
                )

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


# def reject_product(request, product_id):
#     product = get_object_or_404(Product, id=product_id)

#     admin_obj = Admin.objects.get(user=request.user)

#     product.status = Product.Status.REMOVED
#     product.moderated_at = timezone.now()
#     product.moderated_by_admin = admin_obj
#     product.save()

#     return redirect("admin_records:approval_request")
from admin_records.models import ModerationLog

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

    # html_content = render_to_string(
    #     "admin_records/emails/product_reject.html",
    #     {
    #         "producer_name": producer_user.name,
    #         "product_name": product.name,
    #         "reason": reason,
    #         "admin_name": admin_obj.user.name,
    #     }
    # )

    # email = EmailMultiAlternatives(
    #     subject=f"Your product '{product.name}' has been rejected",
    #     body="Your email client does not support HTML emails.",
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     to=[producer_user.email],
    # )
    # email.attach_alternative(html_content, "text/html")
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


# ------------ EMAILS


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
