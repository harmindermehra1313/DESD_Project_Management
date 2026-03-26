from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from orders.models import Order


@login_required
def order_history_page(request):
    recurring_choices = [
        ("true", "Yes"),
        ("false", "No"),
    ]

    return render(
        request,
        "orders/order_history.html",
        {
            "order_status_choices": Order.Status.choices,
            "fulfilment_choices": Order.DeliveryOrCollection.choices,
            "recurring_choices": recurring_choices,
        },
    )