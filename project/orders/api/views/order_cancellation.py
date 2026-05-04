from django.core.exceptions import ObjectDoesNotExist

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.api.serializers.order_cancellation import (
    CustomerOrderCancellationSerializer,
)
from orders.services.customer_cancellation import (
    CustomerCancellationError,
    cancel_order_as_customer,
)
from orders.services.order_status import get_order_status_context


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_customer_order(request, order_id):
    serializer = CustomerOrderCancellationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    reason = serializer.validated_data.get("reason", "")

    try:
        order = cancel_order_as_customer(
            order_id=order_id,
            customer=request.user,
            reason=reason,
        )

    except ObjectDoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Order not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except CustomerCancellationError as exc:
        return Response(
            {
                "success": False,
                "error": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    status_context = get_order_status_context(order)
    return Response(
        {
            "success": True,
            "message": "Order cancelled successfully.",
            "order": {
                "id": order.id,
                "status": status_context["status_code"],
                "status_display": status_context["status_display"],
                "status_key": status_context["status_key"],
                "is_partially_cancelled": status_context["is_partially_cancelled"],
                "can_customer_cancel": status_context["can_customer_cancel"],
                "cancelled_at": order.cancelled_at,
                "cancelled_by": order.cancelled_by_id,
                "cancellation_reason": order.cancellation_reason,
            },
        },
        status=status.HTTP_200_OK,
    )
