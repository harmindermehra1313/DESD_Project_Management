from django import forms
from django.contrib import admin
from django.utils import timezone

from reviews.models import Review


class ReviewModerationAdminForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["status"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    form = ReviewModerationAdminForm

    list_display = (
        "id",
        "product",
        "customer",
        "rating",
        "status",
        "created_at",
        "moderated_at",
    )
    list_filter = ("status", "rating", "created_at", "moderated_at")
    search_fields = (
        "title",
        "text",
        "product__name",
        "customer__user__email",
        "customer__user__name",
    )

    readonly_fields = (
        "product",
        "customer",
        "order",
        "order_item",
        "rating",
        "title",
        "text",
        "anonymous",
        "created_at",
        "moderated_by_admin",
        "moderated_at",
    )

    fields = (
        "product",
        "customer",
        "order",
        "order_item",
        "rating",
        "title",
        "text",
        "anonymous",
        "status",
        "moderated_by_admin",
        "moderated_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def changelist_view(self, request, extra_context=None):
        if not request.GET:
            query = request.GET.copy()
            query["status__exact"] = Review.Status.FLAGGED
            request.GET = query
            request.META["QUERY_STRING"] = request.GET.urlencode()
    
        return super().changelist_view(request, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        admin_profile = getattr(request.user, "admin_profile", None)
        obj.moderated_by_admin = admin_profile
        obj.moderated_at = timezone.now()
        super().save_model(request, obj, form, change)
