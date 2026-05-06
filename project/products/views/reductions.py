from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from ..models import Inventory, InventoryUpdateHistory
from django.db.models import Q, Exists, OuterRef

@login_required
def manage_reductions(request):
    """Render the reductions management page."""
    today = timezone.now().date()
    now = timezone.now()
    producer = request.user.producer_profile

    available_inventory = Inventory.objects.filter(
        product__producer=producer,
        status=Inventory.BatchStatus.ACTIVE,
        remaining_quantity__gt=0,
        expiry_date__gte=today,
        surplus_status=Inventory.SurplusStatus.NONE
    ).select_related("product")

    expired_use_by = Inventory.objects.filter(
        product__producer=producer,
        expiry_type=Inventory.ExpiryType.USE_BY,
        expiry_date__lt=today
    ).select_related("product")

    expired_best_before = Inventory.objects.filter(
        product__producer=producer,
        expiry_type=Inventory.ExpiryType.BEST_BEFORE,
        expiry_date__lt=today
    ).select_related("product")

    active_reductions = Inventory.objects.filter(
        product__producer=producer,
        status=Inventory.BatchStatus.ACTIVE,
        surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE,
        surplus_expiry__gt=now
    ).select_related("product")

    has_reduction_event = InventoryUpdateHistory.objects.filter(
        inventory=OuterRef('pk'),
        event_type__in=["reduction_started", "reduction_ended"]
    )

    past_reductions = Inventory.objects.filter(
        product__producer=producer,
        #surplus_status=Inventory.SurplusStatus.NONE
    ).annotate(
        had_reduction=Exists(has_reduction_event)
    ).filter(
        had_reduction=True
    ).select_related("product")

    # Attach last valid recution values from history
    for r in past_reductions:
        end_event = InventoryUpdateHistory.objects.filter(
            inventory=r,
            event_type="reduction_ended"
        ).order_by("-changed_at").first()

        if end_event:
            r.last_discount = end_event.snapshot_discount
            r.last_expiry = end_event.snapshot_expiry
            r.last_note = end_event.snapshot_note
            r.ended_at = end_event.changed_at
            r.ended_reason = end_event.ended_reason
        else:
            # Should not happen, but safe fallback
            r.last_discount = None
            r.last_expiry = None
            r.last_note = None
            r.ended_at = None
            r.ended_reason = None

    context = {
        "available_products": available_inventory,
        "expired_use_by_products": expired_use_by,
        "expired_best_before_products": expired_best_before,
        "active_reductions": active_reductions,
        "past_reductions": past_reductions,
    }

    return render(request, "products/reductions.html", context)