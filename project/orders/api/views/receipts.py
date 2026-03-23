"""
orders/api/views/receipts.py

Purpose:
Provide receipt detail and receipt PDF download endpoints.
"""

from __future__ import annotations

from django.http import FileResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.serializers.receipts import ReceiptResponseSerializer
from orders.services.receipt_service import build_receipt_pdf, get_receipt_data


class ReceiptDetailApiView(APIView):
    """
    Return a completed-order receipt for the authenticated user.

    Access rules:
    - user must be authenticated
    - order must belong to the authenticated user
    - order must be completed
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id: int, *args, **kwargs):
        payload = get_receipt_data(user=request.user, order_id=order_id)
        serializer = ReceiptResponseSerializer(payload)
        return Response(serializer.data)


class ReceiptDownloadPdfApiView(APIView):
    """
    Generate and download a receipt PDF for a completed order.

    Access rules:
    - user must be authenticated
    - order must belong to the authenticated user
    - order must be completed
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id: int, *args, **kwargs):
        order, pdf_buffer = build_receipt_pdf(user=request.user, order_id=order_id)

        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"receipt-{order.unique_reference}.pdf",
            content_type="application/pdf",
        )
