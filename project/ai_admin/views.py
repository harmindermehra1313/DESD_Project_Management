import os

from BRFN.decorators import admin_required
from django.shortcuts import render, redirect
from django.db.models import Count, Avg
from .models import AIUsage, ClassifierModel
from django.contrib import messages

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
    all_models = ClassifierModel.objects.order_by("-uploaded_at")

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
        "all_models": all_models,
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
            messages.error(request, "All fields are required.")
            return redirect("ai_admin:dashboard")
        
        allowed_ext = {".pth", ".pt", ".bin"}
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in allowed_ext:
            messages.error(request, "Invalid model file type.")
            return redirect("ai_admin:dashboard")

        # Create and activate the new model
        model_obj = ClassifierModel.objects.create(
            name=name,
            version=version,
            file=file,
            is_active=True
        )

        messages.success(request, f"Model '{name}' (v{version}) uploaded and activated.")
        return redirect("ai_admin:dashboard")

    return redirect("ai_admin:dashboard")

@admin_required
def activate_model(request, model_id):
    model = ClassifierModel.objects.filter(id=model_id).first()
    if not model:
        messages.error(request, "Model not found.")
        return redirect("ai_admin:dashboard")

    # Activate this model
    model.is_active = True
    model.save()

    # Clear cached PyTorch model so next request loads the new one
    from products.views.freshness_check import _model
    _model = None

    messages.success(request, f"Activated model {model.name} (v{model.version}).")
    return redirect("ai_admin:dashboard")
