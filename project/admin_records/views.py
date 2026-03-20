# from datetime import datetime, date
# from decimal import Decimal
# import csv
# from django.shortcuts import render
# from django.http import HttpResponse
# from django.db.models import Sum
# from BRFN.decorators import admin_required

# from orders.models import Order, ProducerOrderSummary
# from accounts.models import User, Producer


# COMMISSION_RATE = Decimal("0.05")
# PRODUCER_RATE = Decimal("0.95")




# @admin_required
# def user_list(request):
#     users = User.objects.all().order_by("-created_at")
#     return render(request, "admin_records/user_list.html", {"users": users})


# @admin_required
# def producer_list(request):
#     producers = Producer.objects.all().order_by("farm_name")
#     return render(request, "admin_records/producer_list.html", {"producers": producers})

# @admin_required
# def index(request):
#     return render(request, "admin_records/index.html")

# # admin_records/views_financial_reports.py
# def _parse_date(value):
#     if not value:
#         return None
#     try:
#         return datetime.strptime(value, "%Y-%m-%d").date()
#     except:
#         return None


# @admin_required
# def financial_reports(request):
#     start_date = _parse_date(request.GET.get("start_date"))
#     end_date = _parse_date(request.GET.get("end_date"))
#     producer_id = request.GET.get("producer")
#     status = request.GET.get("status")

#     orders = Order.objects.all().prefetch_related("producer_summaries", "producer_summaries__producer")

#     if start_date:
#         orders = orders.filter(order_date__date__gte=start_date)
#     if end_date:
#         orders = orders.filter(order_date__date__lte=end_date)
#     if status:
#         orders = orders.filter(status=status)

#     order_rows = []
#     total_order_value = Decimal("0.00")
#     total_commission_calc = Decimal("0.00")
#     total_commission_recorded = Decimal("0.00")
#     total_producer_payout = Decimal("0.00")

#     for order in orders:
#         order_total = order.final_total_price
#         commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
#         commission_recorded = order.total_commission.quantize(Decimal("0.01"))
#         producer_payout_total = (order_total - commission_calc).quantize(Decimal("0.01"))

#         total_order_value += order_total
#         total_commission_calc += commission_calc
#         total_commission_recorded += commission_recorded
#         total_producer_payout += producer_payout_total

#         producer_summaries = order.producer_summaries.all()
#         if producer_id:
#             producer_summaries = producer_summaries.filter(producer_id=producer_id)

#         producer_breakdown = [
#             {
#                 "producer_name": ps.producer.farm_name,
#                 "subtotal": ps.subtotal,
#                 "commission_total": ps.commission_total,
#                 "payout_amount": ps.payout_amount,
#             }
#             for ps in producer_summaries
#         ]

#         order_rows.append({
#             "order": order,
#             "order_total": order_total,
#             "commission_calc": commission_calc,
#             "commission_recorded": commission_recorded,
#             "producer_payout_total": producer_payout_total,
#             "producer_breakdown": producer_breakdown,
#         })

#     today = date.today()
#     ytd_orders = Order.objects.filter(order_date__year=today.year)
#     ytd_total = ytd_orders.aggregate(s=Sum("final_total_price"))["s"] or Decimal("0.00")
#     ytd_commission_calc = (ytd_total * COMMISSION_RATE).quantize(Decimal("0.01"))

#     producers = Producer.objects.all()

#     return render(request, "admin_records/financial_reports.html", {
#         "order_rows": order_rows,
#         "total_order_value": total_order_value.quantize(Decimal("0.01")),
#         "total_commission_calc": total_commission_calc.quantize(Decimal("0.01")),
#         "total_commission_recorded": total_commission_recorded.quantize(Decimal("0.01")),
#         "total_producer_payout": total_producer_payout.quantize(Decimal("0.01")),
#         "ytd_total": ytd_total.quantize(Decimal("0.01")),
#         "ytd_commission_calc": ytd_commission_calc,
#         "producers": producers,
#         "selected_producer": int(producer_id) if producer_id else None,
#         "start_date": start_date,
#         "end_date": end_date,
#         "status": status or "",
#     })


# @admin_required
# def financial_reports_csv(request):
#     start_date = _parse_date(request.GET.get("start_date"))
#     end_date = _parse_date(request.GET.get("end_date"))
#     producer_id = request.GET.get("producer")

#     if producer_id in ["", "None", None]:
#         producer_id = None
#     else:
#         producer_id = int(producer_id)
#     status = request.GET.get("status")

#     orders = Order.objects.all().prefetch_related("producer_summaries", "producer_summaries__producer")

#     if start_date:
#         orders = orders.filter(order_date__date__gte=start_date)
#     if end_date:
#         orders = orders.filter(order_date__date__lte=end_date)
#     if status:
#         orders = orders.filter(status=status)

#     response = HttpResponse(content_type="text/csv")
#     response["Content-Disposition"] = 'attachment; filename="commission_report.csv"'

#     writer = csv.writer(response)
#     writer.writerow([
#         "Order ID", "Reference", "Date", "Status",
#         "Order Total", "Commission (5%)", "Commission Recorded",
#         "Producer", "Subtotal", "Producer Commission", "Producer Payout"
#     ])

#     for order in orders:
#         order_total = order.final_total_price
#         commission_calc = (order_total * COMMISSION_RATE).quantize(Decimal("0.01"))
#         commission_recorded = order.total_commission.quantize(Decimal("0.01"))

#         producer_summaries = order.producer_summaries.all()
#         if producer_id:
#             producer_summaries = producer_summaries.filter(producer_id=producer_id)

#         if not producer_summaries.exists():
#             writer.writerow([
#                 order.id, order.unique_reference, order.order_date, order.status,
#                 order_total, commission_calc, commission_recorded,
#                 "", "", "", ""
#             ])
#         else:
#             for ps in producer_summaries:
#                 writer.writerow([
#                     order.id, order.unique_reference, order.order_date, order.status,
#                     order_total, commission_calc, commission_recorded,
#                     ps.producer.farm_name, ps.subtotal, ps.commission_total, ps.payout_amount
#                 ])

#     return response
from datetime import datetime, date
from decimal import Decimal
import csv

from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Sum
from django.template.loader import render_to_string

from BRFN.decorators import admin_required
from orders.models import Order
from accounts.models import User, Producer

# from weasyprint import HTML  # make sure WeasyPrint is installed


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
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.http import HttpResponse


@admin_required
def financial_reports_pdf(request):
    # Reuse your existing filtering logic
    context = _build_financial_context(request)

    # Load PDF template
    template = get_template("admin_records/financial_report_pdf.html")
    html = template.render(context)

    # Prepare PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="financial_report.pdf"'

    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)

    return response