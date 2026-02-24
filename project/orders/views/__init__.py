from django.shortcuts import render
from .checkout import fake_add_to_cart, checkout, order_success

def index(request):
    return render(request, 'orders/index.html')