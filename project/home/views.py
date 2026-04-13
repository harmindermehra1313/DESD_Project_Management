from django.shortcuts import render, redirect
from BRFN.decorators import admin_required, producer_required
from notifications.models import Notification
from notifications.services.notifications import NotificationService

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
    ).order_by('-created_at')[:20] # latest 20

    unread_count = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True
    ).count()
    
    return render(request, "home/producer.html", {
        "notifications": notifications,
        "unread_count": unread_count,
    })

@producer_required
def mark_all_notifications_read(request):
    if request.method == "POST":
        NotificationService.mark_all_read(request.user)
    return redirect('producer')
