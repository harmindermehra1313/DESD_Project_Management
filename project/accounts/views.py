from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.http import HttpResponse
from orders.models import ProducerOrderSummary, OrderItem
from django.db.models import Prefetch
from accounts.models import Producer

# Create your views here.
def register(request):
    return render(request, "accounts/register.html")

def login(request):
    return render(request, "accounts/login.html")







def producer_dashboard(request):
    
    # the first existing producer in PostgreSQL database
    producer = Producer.objects.first()

    # Checks if database is empty
    if not producer:
        return HttpResponse(
            "No producers found in the database! "
            "Please create a Producer (and some orders) via the Django Admin or shell before testing this page."
        )
    
    #Temp auto-login 
    if request.user != producer.user:
        auth_login(request, producer.user)
        print(f"Auto-logged in as EXISTING producer: {producer.user.email}")

    # Fetch orders for logged in producer
    summaries = ProducerOrderSummary.objects.filter(
        producer=producer
    ).select_related(
        'order', 
        'order__user', 
        'order__delivery_address'
    ).prefetch_related(
        Prefetch(
            'order__items', 
            queryset=OrderItem.objects.filter(producer=producer).select_related('product'),
            to_attr='my_items' 
        )
    ).order_by('delivery_date')

    context = {
        'summaries': summaries,
    }
    
    return render(request, "accounts/producer_dashboard.html", context)

# TBC - loads placeholder form based on selected role but doesn't save anything
# def register(request):
#     role = request.GET.get("role", "customer")

#     if request.method == "POST":
#         # TBC - save, currently print
#         print("Received POST for role:", request.POST.get("role"))
#         print("Form data:", request.POST)
#         return render(request, "accounts/register_success.html")

#     return render(request, "accounts/register.html", {
#         "role": role,
#     })