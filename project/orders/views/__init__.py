from django.shortcuts import render
from .checkout import checkout, order_success
from .order_history import order_history_page

def index(request):
    return render(request, 'orders/index.html')