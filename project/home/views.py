from django.shortcuts import render, redirect
from BRFN.decorators import admin_required, producer_required
from notifications.models import Notification
from products.models import Product
from orders.models import Order, OrderItem
from notifications.services.notifications import NotificationService
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

def home(request):
    return render(request, "home/home.html")

@admin_required
def dashboard(request):
    return render(request, "home/dashboard.html")

@producer_required
def producer(request):
    producer = request.user.producer_profile

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10] # latest 10

    unread_count = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True
    ).count()

    # Sales stats
    last_30_orders = Order.objects.filter(
        items__product__producer=producer,
        order_date__gte=timezone.now() - timedelta(days=30)
    ).distinct()

    total_revenue = sum(o.total_price for o in last_30_orders)
    total_orders = last_30_orders.count()
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # All-time stats
    all_time_orders = Order.objects.filter(
        items__product__producer=producer
    ).distinct()

    all_time_revenue = sum(o.total_price for o in all_time_orders)
    all_time_order_count = all_time_orders.count()
    all_time_avg_order_value = (
        all_time_revenue / all_time_order_count if all_time_order_count > 0 else 0
    )

    # Best-selling products
    best_sellers = (
        OrderItem.objects
        .filter(product__producer=producer)
        .values('product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    # Low stock products
    products = Product.objects.filter(producer=producer)
    low_stock = [p for p in products if p.computed_total_stock <= p.low_stock_threshold]

    # Order statistics
    producer_orders = Order.objects.filter(
        items__product__producer=producer
    ).distinct()

    pending_orders = producer_orders.filter(status="PEN")
    completed_orders = producer_orders.filter(status="CMP")
    cancelled_orders = producer_orders.filter(status="CAN")

    # Upcoming orders (future recurring orders)
    upcoming_orders = producer_orders.filter(
        order_date__gte=timezone.now()
    ).order_by("order_date")[:5]

    producer_orders = Order.objects.filter(
        items__product__producer=producer
    ).distinct()

    producer_orders_count = producer_orders.count() or 0

    # Order status counts for graph
    pending_count = pending_orders.count()
    completed_count = completed_orders.count()
    cancelled_count = cancelled_orders.count()
    total_status_count = pending_count + completed_count + cancelled_count
    thirty_days_ago = timezone.now() - timedelta(days=30)

    pending_30 = producer_orders.filter(
        status="PEN",
        order_date__gte=thirty_days_ago
    ).count()

    completed_30 = producer_orders.filter(
        status="CMP",
        order_date__gte=thirty_days_ago
    ).count()

    cancelled_30 = producer_orders.filter(
        status="CAN",
        order_date__gte=thirty_days_ago
    ).count()

    return render(request, "home/producer.html", {
        "notifications": notifications,
        "unread_count": unread_count,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "best_sellers": best_sellers,
        "low_stock": low_stock,
        "all_time_revenue": all_time_revenue,
        "all_time_order_count": all_time_order_count,
        "all_time_avg_order_value": all_time_avg_order_value,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "upcoming_orders": upcoming_orders,
        "producer_orders_count": producer_orders_count,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "total_status_count": total_status_count,
        "pending_30": pending_30,
        "completed_30": completed_30,
        "cancelled_30": cancelled_30,
    })

@producer_required
def mark_all_notifications_read(request):
    if request.method == "POST":
        NotificationService.mark_all_read(request.user)
    return redirect('home:producer')

@producer_required
def mark_notification_read(request, pk):
    note = Notification.objects.filter(pk=pk, user=request.user).first()
    if note:
        NotificationService.mark_read(note)

    # TBC for now return to the producer dashboard
    return redirect("home:producer")