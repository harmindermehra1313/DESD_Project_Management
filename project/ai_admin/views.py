from BRFN.decorators import admin_required
from django.shortcuts import render, redirect
from django.db.models import Count, Avg
from .models import AIUsage, ClassifierModel

@admin_required
def dashboard(request):
    # Summary stats 
    total_calls = AIUsage.objects.count()
    recommender_calls = AIUsage.objects.filter(model_type="REC").count()
    classifier_calls = AIUsage.objects.filter(model_type="CLS").count()

    # Component breakdown for recommender 
    component_counts = (
        AIUsage.objects
        .filter(model_type="REC")
        .values("component")
        .annotate(count=Count("id"))
    )

    component_labels = [c["component"] for c in component_counts]
    component_values = [c["count"] for c in component_counts]

    # Execution time averages 
    exec_labels = ["Recommender", "Classifier"]
    exec_values = [
        AIUsage.objects.filter(model_type="REC").aggregate(avg=Avg("execution_time_ms"))["avg"] or 0,
        AIUsage.objects.filter(model_type="CLS").aggregate(avg=Avg("execution_time_ms"))["avg"] or 0,
    ]

    # Active model 
    active_model = ClassifierModel.objects.filter(is_active=True).first()

    # Recent logs 
    recent_logs = AIUsage.objects.order_by("-created_at")[:20]

    context = {
        "total_calls": total_calls,
        "recommender_calls": recommender_calls,
        "classifier_calls": classifier_calls,
        "component_labels": component_labels,
        "component_values": component_values,
        "exec_labels": exec_labels,
        "exec_values": exec_values,
        "active_model": active_model,
        "recent_logs": recent_logs,
    }

    return render(request, "ai_admin/dashboard.html", context)

@admin_required
def upload_model(request):
    if request.method == "POST":
        name = request.POST.get("name")
        version = request.POST.get("version")
        file = request.FILES.get("file")

        if not (name and version and file):
            return redirect("ai_admin:dashboard")

        # Create and activate the new model
        model_obj = ClassifierModel.objects.create(
            name=name,
            version=version,
            file=file,
            is_active=True
        )

        return redirect("ai_admin:dashboard")

    return redirect("ai_admin:dashboard")
