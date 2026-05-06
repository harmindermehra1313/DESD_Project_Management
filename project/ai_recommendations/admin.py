from django.contrib import admin

from .models import ProductInteraction


@admin.register(ProductInteraction)
class ProductInteractionAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "user",
        "session_key",
        "event_type",
        "source",
        "created_at",
    )
    list_filter = (
        "event_type",
        "source",
        "created_at",
    )
    search_fields = (
        "product__name",
        "user__email",
        "user__name",
        "session_key",
    )
    readonly_fields = ("created_at",)
