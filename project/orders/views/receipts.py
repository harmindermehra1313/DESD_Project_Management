from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework.exceptions import ValidationError

from orders.services.receipt_service import get_receipt_data


@login_required
def receipt_detail_page(request, order_id: int):
    try:
        get_receipt_data(user=request.user, order_id=order_id)
    except ValidationError:
        return render(request, "orders/404.html", status=404)
    except Exception:
        return render(request, "orders/404.html", status=404)

    return render(
        request,
        "orders/receipt_detail.html",
        {
            "order_id": order_id,
        },
    )