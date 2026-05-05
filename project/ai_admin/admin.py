from django.contrib import admin
from .models import AIUsage, ClassifierModel


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    list_display = (
        "model_type",
        "component",
        "model_version",
        "user",
        "execution_time_ms",
        "created_at",
    )
    list_filter = ("model_type", "component", "model_version", "created_at")
    search_fields = ("user__email", "model_version")
    ordering = ("-created_at",)


@admin.register(ClassifierModel)
class ClassifierModelAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "uploaded_at", "is_active")
    list_filter = ("is_active", "uploaded_at")
    search_fields = ("name", "version")

    actions = ["activate_model"]

    def activate_model(self, request, queryset):
        queryset.update(is_active=False)
        obj = queryset.first()
        obj.is_active = True
        obj.save()
        self.message_user(request, f"Activated model: {obj.name} (v{obj.version})")

    activate_model.short_description = "Activate selected model"
