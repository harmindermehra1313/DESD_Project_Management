from django.shortcuts import render
from .checkout import checkout, order_success

def index(request):
    return render(request, 'orders/index.html')