from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def receipt_detail_page(request, order_id: int):
    return render(
        request,
        "orders/receipt_detail.html",
        {
            "order_id": order_id,
        },
    )