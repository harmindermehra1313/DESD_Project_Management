from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from BRFN.decorators import producer_required
from django.db.models import Sum, F, Q
from django.utils.timezone import now
from datetime import timedelta, date, datetime
from orders.models import Order, OrderItem, ProducerOrderSummary
from payments.models import Payment
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from accounts.services.pdf_builder import PDFBuilder
import csv
import io
import zipfile

def get_tax_year_range(today):
    """Return (start_date, end_date) for the UK tax year containing 'today'."""
    year = today.year
    tax_year_start = date(year, 4, 6)
    if today < tax_year_start:
        tax_year_start = date(year - 1, 4, 6)
    tax_year_end = tax_year_start.replace(year=tax_year_start.year + 1) - timedelta(days=1)
    return tax_year_start, tax_year_end

def get_week_ranges_for_tax_year(start, end):
    """Return a list of (week_start, week_end) tuples covering the tax year."""
    weeks = []
    current = start

    while current <= end:
        week_start = current
        week_end = min(current + timedelta(days=6), end)
        weeks.append((week_start, week_end))
        current = week_end + timedelta(days=1)

    return weeks

@login_required
@producer_required
def producer_payments_view(request):
    producer = request.user.producer_profile

    # -----------------------------------------
    # Check if a week was requested manually
    # -----------------------------------------
    week_param = request.GET.get("week")
    today = now().date()

    if week_param:
        try:
            week_start_str, week_end_str = week_param.split("_")
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            week_end = datetime.strptime(week_end_str, "%Y-%m-%d").date()
        except ValueError:
            return HttpResponse("Invalid week format", status=400)
    else:
        # Most recently completed week: previous Monday–Sunday
        weekday = today.weekday() # Monday=0
        week_end = today - timedelta(days=weekday + 1)
        week_start = week_end - timedelta(days=6)

    previous_week_start = week_start - timedelta(days=7)
    previous_week_end = week_end - timedelta(days=7)
    next_week_start = week_start + timedelta(days=7)
    next_week_end = week_end + timedelta(days=7)

    previous_week_id = f"{previous_week_start}_{previous_week_end}"
    next_week_id = f"{next_week_start}_{next_week_end}"

    # -----------------------------
    # Fetch weekly order summaries
    # -----------------------------
    completed_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    )

    pending_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
    ).exclude(status=ProducerOrderSummary.Status.COMPLETED)
    pending_total = pending_summaries.aggregate(total=Sum("payout_amount"))["total"] or 0

    # Totals (completed only)
    week_total = completed_summaries.aggregate(total=Sum("subtotal"))["total"] or 0
    week_commission = completed_summaries.aggregate(total=Sum("commission_total"))["total"] or 0
    week_payout = completed_summaries.aggregate(total=Sum("payout_amount"))["total"] or 0

    # Completed week totals by payment method
    card_total = completed_summaries.filter(
        order__payments__payment_method="CRD"
    ).aggregate(total=Sum("payout_amount"))["total"] or 0

    cash_total = completed_summaries.filter(
        order__payments__payment_method="COD"
    ).aggregate(total=Sum("payout_amount"))["total"] or 0

    # Pending week totals by payment method
    pending_card_total = pending_summaries.filter(
        order__payments__payment_method="CRD"
    ).aggregate(total=Sum("payout_amount"))["total"] or 0

    pending_cash_total = pending_summaries.filter(
        order__payments__payment_method="COD"
    ).aggregate(total=Sum("payout_amount"))["total"] or 0

    # -----------------------------
    # Build order breakdown lists
    # -----------------------------
    def build_order_list(summaries):
        orders = []
        for summary in summaries.select_related("order"):
            order = summary.order
            items = OrderItem.objects.filter(order=order).annotate(
                product_name=F("product__name")
            )
            orders.append({
                "reference": order.unique_reference,
                "date": order.order_date.date(),
                "customer_id": order.user.id if order.user else "Guest",
                "customer_name": (
                    f"{order.user.name}"
                    if order.user else "Guest"
                ),
                "items": [
                    {"product_name": i.product_name, "quantity": i.quantity}
                    for i in items
                ],
                "total": summary.subtotal,
                "payment_method": order.payment.payment_method if hasattr(order, "payment") else None,
                "commission": summary.commission_total,
                "payout": summary.payout_amount,
                "status": summary.status,
            })
        return orders

    completed_orders = build_order_list(completed_summaries)
    pending_orders = build_order_list(pending_summaries)

    # -----------------------------
    # Payment status
    # -----------------------------
    completed_order_ids = completed_summaries.values_list("order_id", flat=True)
    total_completed = completed_summaries.count()

    successful_payments = Payment.objects.filter(
        order_id__in=completed_order_ids,
        payment_status=Payment.Status.SUCCESS,
    ).count()

    if total_completed == 0:
        payment_status = "no_completed"
    elif successful_payments == total_completed:
        payment_status = "processed"
    else:
        payment_status = "pending"

    # -----------------------------
    # Tax year running total (completed only)
    # -----------------------------
    year = today.year
    tax_year_start = date(year, 4, 6)
    if today < tax_year_start:
        tax_year_start = date(year - 1, 4, 6)
    tax_year_end = tax_year_start.replace(year=tax_year_start.year + 1) - timedelta(days=1)

    tax_year_total = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[tax_year_start, tax_year_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    ).aggregate(total=Sum("payout_amount"))["total"] or 0

    # -----------------------------
    # Context for template
    # -----------------------------
    context = {
        "week_start": week_start,
        "week_end": week_end,
        "week_total": week_total,
        "week_commission": week_commission,
        "week_payout": week_payout,
        "payment_status": payment_status,
        "pending_total": pending_total,

        "card_total": card_total,
        "cash_total": cash_total,
        "pending_card_total": pending_card_total,
        "pending_cash_total": pending_cash_total,

        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "has_completed": bool(completed_orders),
        "has_pending": bool(pending_orders),
        "anonymise": True,

        "tax_year_total": tax_year_total,
        "tax_year_start": tax_year_start,
        "tax_year_end": tax_year_end,

        "week_id": f"{week_start}_{week_end}",
        "previous_week_id": previous_week_id,
        "next_week_id": next_week_id,
    }

    return render(request, "accounts/producer/producer_payments.html", context)
@login_required
@producer_required
def download_payment_report_view(request, week_id):
    """
    Generates a PDF payment report for the selected week.
    week_id format: 'YYYY-MM-DD_YYYY-MM-DD'
    """
    try:
        week_start_str, week_end_str = week_id.split("_")
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        week_end = datetime.strptime(week_end_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Invalid week ID format.", status=400)

    producer = request.user.producer_profile

    # Fetch summaries
    completed_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    )

    upcoming_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
    ).exclude(
        status__in=[
        ProducerOrderSummary.Status.COMPLETED,
        ProducerOrderSummary.Status.CANCELLED,
    ])

    # Totals
    week_total = completed_summaries.aggregate(total=Sum("subtotal"))["total"] or 0
    week_commission = completed_summaries.aggregate(total=Sum("commission_total"))["total"] or 0
    week_payout = completed_summaries.aggregate(total=Sum("payout_amount"))["total"] or 0

    upcoming_total = upcoming_summaries.aggregate(total=Sum("payout_amount"))["total"] or 0

    # Card vs Cash totals
    card_total = completed_summaries.filter(order__payments__payment_method="CRD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    cash_total = completed_summaries.filter(order__payments__payment_method="COD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    upcoming_card_total = upcoming_summaries.filter(order__payments__payment_method="CRD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    upcoming_cash_total = upcoming_summaries.filter(order__payments__payment_method="COD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    # Payment status logic
    completed_order_ids = completed_summaries.values_list("order_id", flat=True)
    total_completed = completed_summaries.count()

    successful_payments = Payment.objects.filter(
        order_id__in=completed_order_ids,
        payment_status=Payment.Status.SUCCESS,
    ).count()

    if total_completed == 0:
        payment_status = "No completed orders"
    elif successful_payments == total_completed:
        payment_status = "Processed"
    else:
        payment_status = "Pending Bank Transfer"

    # PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="payment_report_{week_id}.pdf"'

    pdf = PDFBuilder(response)

    # Header
    pdf.heading("Weekly Payment Report")
    pdf.text(f"Producer: {producer.user.name}")
    pdf.text(f"Week: {week_start} → {week_end}")
    pdf.text(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}")
    pdf.hr()

    # Summary box
    pdf.subheading("Summary")
    pdf.shaded_box([
        f"Completed Orders (Earned This Week): £{week_total}",
        f"Network Commission (5%): £{week_commission}",
        f"Producer Payout (95%): £{week_payout}",
        f"Card Earnings: £{card_total}",
        f"Cash Earnings: £{cash_total}",
    ])

    # Upcoming orders summary
    if upcoming_total > 0:
        pdf.subheading("Upcoming Orders (Future Earnings)")
        pdf.shaded_box([
            f"Total Future Earnings: £{upcoming_total}",
            f"Upcoming Card Earnings: £{upcoming_card_total}",
            f"Upcoming Cash Earnings: £{upcoming_cash_total}",
        ])

    # Payment status
    pdf.subheading("Payment Status")
    pdf.text(payment_status)
    pdf.hr()

    # Completed Orders Table
    pdf.subheading("Completed Orders (Earned This Week)")
    pdf.text("These orders have been completed and contribute to this week's payout.")

    completed_rows = []
    for summary in completed_summaries:
        completed_rows.append([
            summary.order.unique_reference,
            summary.order.order_date.date(),
            f"£{summary.subtotal}",
            f"£{summary.commission_total}",
            f"£{summary.payout_amount}",
        ])

    if completed_rows:
        pdf.table(
            ["Order Ref", "Date", "Total", "Commission", "Payout"],
            completed_rows
        )
    else:
        pdf.text("No completed orders for this week.")

    # Upcoming Orders Table
    pdf.subheading("Upcoming Orders (Future Earnings)")
    pdf.text("These orders are scheduled for future delivery or collection and will be paid once completed.")

    upcoming_rows = []
    for summary in upcoming_summaries:
        upcoming_rows.append([
            summary.order.unique_reference,
            summary.order.order_date.date(),
            f"£{summary.subtotal}",
            f"£{summary.commission_total}",
            f"£{summary.payout_amount}",
        ])

    if upcoming_rows:
        pdf.table(
            ["Order Ref", "Date", "Total", "Commission", "Payout"],
            upcoming_rows
        )
    else:
        pdf.text("No upcoming orders for this week.")

    pdf.save()
    return response

@login_required
@producer_required
def download_payment_csv_view(request, week_id):
    try:
        week_start_str, week_end_str = week_id.split("_")
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        week_end = datetime.strptime(week_end_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Invalid week ID format.", status=400)

    producer = request.user.producer_profile

    # Fetch summaries
    completed_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    )

    upcoming_summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[week_start, week_end],
    ).exclude(
        status__in=[
        ProducerOrderSummary.Status.COMPLETED,
        ProducerOrderSummary.Status.CANCELLED,
    ])

    # Payment status logic
    completed_order_ids = completed_summaries.values_list("order_id", flat=True)
    total_completed = completed_summaries.count()

    successful_payments = Payment.objects.filter(
        order_id__in=completed_order_ids,
        payment_status=Payment.Status.SUCCESS,
    ).count()

    if total_completed == 0:
        payment_status = "No completed orders"
    elif successful_payments == total_completed:
        payment_status = "Processed"
    else:
        payment_status = "Pending Bank Transfer"

    # CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="payment_report_{week_id}.csv"'
    )

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        "Order Reference",
        "Date",
        "Customer (Anonymised)",
        "Items Sold",
        "Order Total (£)",
        "Commission (£)",
        "Payout (£)",
        "Payment Method",
        "Order Status",
        "Financial Status",
    ])

    # Completed orders
    for summary in completed_summaries:
        order = summary.order

        items = OrderItem.objects.filter(order=order).annotate(
            product_name=F("product__name")
        )
        items_str = "; ".join(f"{i.quantity} x {i.product_name}" for i in items)

        payment_method = (
            order.payment.payment_method if hasattr(order, "payment") else None
        )
        payment_label = "Card" if payment_method == "CRD" else "Cash"

        writer.writerow([
            order.unique_reference,
            order.order_date.date(),
            f"Customer #{order.user.id}" if order.user else "Guest",
            items_str,
            f"{summary.subtotal:.2f}",
            f"{summary.commission_total:.2f}",
            f"{summary.payout_amount:.2f}",
            payment_label,
            "Completed (Earned)",
            payment_status,
        ])

    # Upcoming orders
    for summary in upcoming_summaries:
        order = summary.order

        items = OrderItem.objects.filter(order=order).annotate(
            product_name=F("product__name")
        )
        items_str = "; ".join(f"{i.quantity} x {i.product_name}" for i in items)

        payment_method = (
            order.payment.payment_method if hasattr(order, "payment") else None
        )
        payment_label = "Card" if payment_method == "CRD" else "Cash"

        writer.writerow([
            order.unique_reference,
            order.order_date.date(),
            f"Customer #{order.user.id}" if order.user else "Guest",
            items_str,
            f"{summary.subtotal:.2f}",
            f"{summary.commission_total:.2f}",
            f"{summary.payout_amount:.2f}",
            payment_label,
            "Upcoming (Not Yet Completed)",
            "Not Applicable",
        ])

    return response

@login_required
@producer_required
def download_tax_year_pdf_view(request):
    today = now().date()
    producer = request.user.producer_profile

    tax_year_start, tax_year_end = get_tax_year_range(today)

    summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[tax_year_start, tax_year_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    )

    # Totals
    total_value = summaries.aggregate(total=Sum("subtotal"))["total"] or 0
    total_commission = summaries.aggregate(total=Sum("commission_total"))["total"] or 0
    total_payout = summaries.aggregate(total=Sum("payout_amount"))["total"] or 0

    card_total = summaries.filter(order__payments__payment_method="CRD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    cash_total = summaries.filter(order__payments__payment_method="COD") \
        .aggregate(total=Sum("payout_amount"))["total"] or 0

    # PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="tax_year_report_{tax_year_start}_{tax_year_end}.pdf"'
    )

    pdf = PDFBuilder(response)

    # Header
    pdf.heading("Tax Year Payment Report")
    pdf.text(f"Producer: {producer.user.name}")
    pdf.text(f"Tax Year: {tax_year_start} → {tax_year_end}")
    pdf.text(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}")
    pdf.hr()

    # Summary box
    pdf.subheading("Summary")
    pdf.shaded_box([
        f"Total Completed Order Value: £{total_value}",
        f"Total Commission: £{total_commission}",
        f"Total Payout: £{total_payout}",
        f"Card Earnings: £{card_total}",
        f"Cash Earnings: £{cash_total}",
    ])

    # Completed Orders Table
    pdf.subheading("Completed Orders (This Tax Year)")
    pdf.text("These orders were completed during the tax year and contribute to your taxable income.")

    rows = []
    for summary in summaries:
        rows.append([
            summary.order.unique_reference,
            summary.order.order_date.date(),
            f"£{summary.subtotal}",
            f"£{summary.commission_total}",
            f"£{summary.payout_amount}",
        ])

    if rows:
        pdf.table(
            ["Order Ref", "Date", "Total", "Commission", "Payout"],
            rows
        )
    else:
        pdf.text("No completed orders in this tax year.")

    pdf.save()
    return response

@login_required
@producer_required
def download_tax_year_csv_view(request):
    today = now().date()
    producer = request.user.producer_profile

    tax_year_start, tax_year_end = get_tax_year_range(today)

    summaries = ProducerOrderSummary.objects.filter(
        producer=producer,
        delivery_date__range=[tax_year_start, tax_year_end],
        status=ProducerOrderSummary.Status.COMPLETED,
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="tax_year_report_{tax_year_start}_{tax_year_end}.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "Order Reference",
        "Date",
        "Customer (Anonymised)",
        "Items Sold",
        "Order Total (£)",
        "Commission (£)",
        "Payout (£)",
        "Payment Method",
    ])

    for summary in summaries:
        order = summary.order

        items = OrderItem.objects.filter(order=order).annotate(
            product_name=F("product__name")
        )
        items_str = "; ".join(f"{i.quantity} x {i.product_name}" for i in items)

        payment_method = order.payment.payment_method if hasattr(order, "payment") else None
        payment_label = "Card" if payment_method == "CRD" else "Cash"

        writer.writerow([
            order.unique_reference,
            order.order_date.date(),
            f"Customer #{order.user.id}" if order.user else "Guest",
            items_str,
            f"{summary.subtotal:.2f}",
            f"{summary.commission_total:.2f}",
            f"{summary.payout_amount:.2f}",
            payment_label,
        ])

    return response


@login_required
@producer_required
def download_tax_year_zip_view(request):
    today = now().date()
    producer = request.user.producer_profile

    tax_year_start, tax_year_end = get_tax_year_range(today)
    weeks = get_week_ranges_for_tax_year(tax_year_start, tax_year_end)

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:

        for week_start, week_end in weeks:
            week_id = f"{week_start}_{week_end}"

            # Generate weekly PDF (using your new PDFBuilder-based function)
            pdf_response = download_payment_report_view(request, week_id)
            zipf.writestr(f"pdf/{week_id}.pdf", pdf_response.content)

            # Generate weekly CSV
            csv_response = download_payment_csv_view(request, week_id)
            zipf.writestr(f"csv/{week_id}.csv", csv_response.content)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="tax_year_reports_{tax_year_start}_to_{tax_year_end}.zip"'
    )
    return response
