from django.shortcuts import render, redirect
from BRFN.decorators import admin_required, producer_required
from notifications.models import Notification
from products.models import Product
from orders.models import Order, OrderItem
from notifications.services.notifications import NotificationService
from django.db.models import Sum
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from accounts.models import User
from products.models import Product
from reviews.models import Review

from django.shortcuts import render
from reviews.models import Review
from admin_records.dashboard_notification_views import get_review_notification_context

def home(request):
    return render(request, "home/home.html")


@producer_required
def producer(request):
    producer = request.user.producer_profile

    # notifications = Notification.objects.filter(
    #     user=request.user
    # ).order_by('-created_at')[:10] # latest 10

    # unread_count = Notification.objects.filter(
    #     user=request.user,
    #     read_at__isnull=True
    # ).count()

    # Notifications with pagination
    notifications_qs = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    paginator = Paginator(notifications_qs, 5) # 5 per page
    page_number = request.GET.get("page")
    notifications = paginator.get_page(page_number)

    unread_count = notifications_qs.filter(read_at__isnull=True).count()

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

    page = request.POST.get("page") or request.GET.get("page") or "1"
    return redirect(f"/producer/?page={page}")


@producer_required
def mark_notification_read(request, pk):
    note = Notification.objects.filter(pk=pk, user=request.user).first()

    if not note:
        return redirect("/producer/")

    NotificationService.mark_read(note)

    page = request.POST.get("page") or request.GET.get("page") or "1"
    producer = request.user.producer_profile

    if note.type == Notification.Type.PRODUCT_ALERT and note.product:
        return redirect(f"/products/producer/products/?open_product={note.product.id}")

    if note.type == Notification.Type.ORDER_UPDATE and note.order:
        if note.order.producer_summaries.filter(producer=producer).exists():
            return redirect(f"/accounts/producer_dashboard/?open_order={note.order.id}")

    if note.type == Notification.Type.RECALL and note.product:
        if note.product.producer == producer:
            return redirect(f"/products/producer/products/?open_product={note.product.id}")

    # Default fallback - SYSTEM, PROMOTION, MESSAGE
    page = request.POST.get("page", 1)
    return redirect(f"home/producer/?page={page}")
    #return redirect("home:producer")





# @admin_required
# def dashboard(request):

#     def get_user_growth(days):
#         start = timezone.now() - timedelta(days=days)
#         qs = (
#             User.objects.filter(created_at__gte=start)
#             .extra(select={'day': "date(created_at)"})
#             .values('day')
#             .annotate(count=Count('id'))
#             .order_by('day')
#         )
#         return {
#             "labels": [str(x["day"]) for x in qs],
#             "values": [x["count"] for x in qs]
#         }


#     user_growth_15 = get_user_growth(15)
#     user_growth_30 = get_user_growth(30)
#     user_growth_365 = get_user_growth(365)

#     today = timezone.now()
#     last_15 = today - timedelta(days=15)
#     last_30 = today - timedelta(days=30)
#     last_year = today - timedelta(days=365)

#     # KPIs
#     # kpi_cards = [
#     #     {"label": "Total Users", "value": User.objects.count()},
#     #     {"label": "New Users (15 days)", "value": User.objects.filter(created_at__gte=last_15).count()},
#     #     {"label": "New Users (30 days)", "value": User.objects.filter(created_at__gte=last_30).count()},
#     #     {"label": "New Users (1 year)", "value": User.objects.filter(created_at__gte=last_year).count()},
#     #     {"label": "Active Accounts", "value": User.objects.filter(is_active=True).count()},
#     #     {"label": "Deactivated Accounts", "value": User.objects.filter(is_active=False).count()},
#     #     {"label": "Customers", "value": User.objects.filter(role="customer").count()},
#     #     {"label": "Producers", "value": User.objects.filter(role="producer").count()},
#     #     {"label": "Business Accounts", "value": User.objects.filter(role="business").count()},
#     #     {"label": "Total Products", "value": Product.objects.count()},
#     #     {"label": "Published Products", "value": Product.objects.filter(status="published").count()},
#     #     {"label": "Pending Products", "value": Product.objects.filter(status="pending").count()},
#     #     {"label": "Flagged Products", "value": Product.objects.filter(status="flagged").count()},
#     #     {"label": "Total Reviews", "value": Review.objects.count()},
#     # ]
#     kpi_cards = [
#     {"label": "Total Users", "value": User.objects.count()},
#     {"label": "Total Products", "value": Product.objects.count()},
#     {"label": "Total Reviews", "value": Review.objects.count()},
# ]

#     # User Growth (last 30 days)
#     user_growth = (
#         User.objects.filter(created_at__gte=last_30)
#         .extra(select={'day': "date(created_at)"})
#         .values('day')
#         .annotate(count=Count('id'))
#         .order_by('day')
#     )

#     user_growth_labels = [str(u["day"]) for u in user_growth]
#     user_growth_values = [u["count"] for u in user_growth]

#     # Account Type Breakdown
#     account_type_labels = ["Customer", "Producer", "Business"]
#     account_type_values = [
#         User.objects.filter(role="customer").count(),
#         User.objects.filter(role="producer").count(),
#         User.objects.filter(role="business").count(),
#     ]

#     # Account Status
#     account_status_labels = ["Active", "Deactivated"]
#     account_status_values = [
#         User.objects.filter(is_active=True).count(),
#         User.objects.filter(is_active=False).count(),
#     ]

#     # Product Status
#     product_status_labels = ["Published", "Pending", "Flagged"]
#     product_status_values = [
#         Product.objects.filter(status="published").count(),
#         Product.objects.filter(status="pending").count(),
#         Product.objects.filter(status="flagged").count(),
#     ]

#     # Review Sentiment
#     review_sentiment_labels = ["Positive", "Neutral", "Negative"]
#     review_sentiment_values = [
#         Review.objects.filter(rating__gte=4).count(),
#         Review.objects.filter(rating=3).count(),
#         Review.objects.filter(rating__lte=2).count(),
#     ]

#     # Recent Users
#     recent_users = User.objects.order_by("-created_at")[:10]

#     return render(request, "home/dashboard.html", {
#         "growth_15": user_growth_15,
#         "growth_30": user_growth_30,
#         "growth_365": user_growth_365,
#         "kpi_cards": kpi_cards,
#         "user_growth_labels": user_growth_labels,
#         "user_growth_values": user_growth_values,
#         "account_type_labels": account_type_labels,
#         "account_type_values": account_type_values,

#         "account_status_labels": account_status_labels,
#         "account_status_values": account_status_values,
#         "product_status_labels": product_status_labels,
#         "product_status_values": product_status_values,
#         "review_sentiment_labels": review_sentiment_labels,
#         "review_sentiment_values": review_sentiment_values,
#         "recent_users": recent_users,
#     })


@admin_required
def dashboard(request):

    # Helper function for user growth
    def get_user_growth(days):
        start = timezone.now() - timedelta(days=days)
        qs = (
            User.objects.filter(created_at__gte=start)
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        return {
            "labels": [str(x["day"]) for x in qs],
            "values": [x["count"] for x in qs]
        }

    # Growth datasets
    growth_15 = get_user_growth(15)
    growth_30 = get_user_growth(30)
    growth_365 = get_user_growth(365)

    # KPIs (only 3)
    kpi_cards = [
        {"label": "Total Users", "value": User.objects.count()},
        {"label": "Total Products", "value": Product.objects.count()},
        {"label": "Total Reviews", "value": Review.objects.count()},
    ]

    # Account Type Breakdown
    account_type_labels = ["Customer", "Producer", "Business"]
    account_type_values = [
        User.objects.filter(role="CUSTOMER").count(),
        User.objects.filter(role="PRODUCER").count(),
        User.objects.filter(role="BUSINESS").count(),
    ]

    # Account Status
    account_status_labels = ["Active", "Deactivated"]
    account_status_values = [
        User.objects.filter(is_active=True).count(),
        User.objects.filter(is_active=False).count(),
    ]

    # Product Status
    product_status_labels = [
        Product.Status.PUBLISHED.label,
        Product.Status.PENDING.label,
        Product.Status.FLAGGED.label,
    ]

    product_status_values = [
    Product.objects.filter(status=Product.Status.PUBLISHED).count(),
    Product.objects.filter(status=Product.Status.PENDING).count(),
    Product.objects.filter(status=Product.Status.FLAGGED).count(),
]


    # Review Sentiment
    review_sentiment_labels = ["Positive", "Neutral", "Negative"]
    review_sentiment_values = [
        Review.objects.filter(rating__gte=4).count(),
        Review.objects.filter(rating=3).count(),
        Review.objects.filter(rating__lte=2).count(),
    ]

    # Recent Users
    recent_users = User.objects.order_by("-created_at")[:10]
    context = get_review_notification_context(request)
    return render(request, "home/dashboard.html", {
        "growth_15": growth_15,
        "growth_30": growth_30,
        "growth_365": growth_365,

        "kpi_cards": kpi_cards,

        "account_type_labels": account_type_labels,
        "account_type_values": account_type_values,

        "account_status_labels": account_status_labels,
        "account_status_values": account_status_values,

        "product_status_labels": product_status_labels,
        "product_status_values": product_status_values,

        "review_sentiment_labels": review_sentiment_labels,
        "review_sentiment_values": review_sentiment_values,

        "recent_users": recent_users,
        
    })
# @staff_member_required
# def admin_records_dashboard(request):
#     context = get_review_notification_context(request)
#     return render(request, "admin_records/index.html", context)
