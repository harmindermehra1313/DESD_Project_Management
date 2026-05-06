from django.contrib.auth.decorators import login_required
from django.http import FileResponse

from orders.services.receipt_service import build_receipt_pdf


@login_required
def receipt_pdf_page(request, order_id):
    order, pdf_buffer = build_receipt_pdf(
        user=request.user,
        order_id=order_id,
    )

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"receipt-{order.unique_reference}.pdf",
        content_type="application/pdf",
    )