import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from products.models import Product, Inventory, InventoryUpdateHistory
from django.contrib.auth.decorators import login_required
from BRFN.decorators import producer_required
from datetime import date, timedelta
from django.db.models import Sum
from django.template.loader import render_to_string
from notifications.services.notifications import NotificationService

#TBC move notifications for low stock to background task

@producer_required
@require_POST
def add_batch(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    # Extract fields
    original_quantity = data.get("original_quantity")
    harvest_date = data.get("harvest_date")
    expiry_date = data.get("expiry_date")
    expiry_type = data.get("expiry_type")

    # Convert dates
    try:
        harvest_date = date.fromisoformat(harvest_date)
        expiry_date = date.fromisoformat(expiry_date)
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date format."})

    # Quantity validation
    try:
        original_quantity = int(original_quantity)
        if not (1 <= original_quantity <= 9999):
            raise ValueError
    except ValueError:
        return JsonResponse({"success": False, "error": "Quantity must be between 1 and 9999."})

    today = date.today()
    last_month = today - timedelta(days=30)

    # Harvest date validation
    if harvest_date > today:
        return JsonResponse({"success": False, "error": "Harvest date cannot be in the future."})

    if harvest_date < last_month:
        return JsonResponse({"success": False, "error": "Harvest date cannot be more than 30 days old."})

    # Expiry date validation
    if expiry_date < today:
        return JsonResponse({"success": False, "error": "Expiry date cannot be in the past."})

    if expiry_date < harvest_date:
        return JsonResponse({"success": False, "error": "Expiry date cannot be before harvest date."})

    # Create the batch
    batch = Inventory.objects.create(
        product=product,
        user=request.user,
        original_quantity=original_quantity,
        remaining_quantity=original_quantity,
        harvest_date=harvest_date,
        expiry_date=expiry_date,
        expiry_type=expiry_type,
        surplus_status=Inventory.SurplusStatus.NONE,
        surplus_discount_percentage=0,
    )

    # Update history log
    InventoryUpdateHistory.objects.create(
        inventory=batch,
        user=request.user,
        field_changed="batch_created",
        old_value=None,
        new_value=f"Qty {batch.original_quantity}, Harvest {batch.harvest_date}, Expiry {batch.expiry_date}",
    )

    total_stock = product.inventory_batches.aggregate(total=Sum('remaining_quantity'))['total'] or 0

    trigger_low_stock_notification(product)

    return JsonResponse({
        "success": True,
        "batch": {
            "id": batch.id,
            "harvest_date": str(batch.harvest_date),
            "expiry_date": batch.expiry_date.isoformat(),
            "expiry_type": batch.expiry_type,
            "remaining_quantity": batch.remaining_quantity,
        },
        "total_stock": total_stock,
    })


@require_POST
@producer_required
def reduce_batch(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    try:
        data = json.loads(request.body)
        batch_id = data.get("batch_id")
        amount = int(data.get("amount"))

        batch = get_object_or_404(Inventory, pk=batch_id, product=product)

        if amount < 1:
            return JsonResponse({"success": False, "error": "Reduction amount must be at least 1."})

        if amount > batch.remaining_quantity:
            return JsonResponse({"success": False, "error": "Cannot reduce more than remaining stock."})

        old_value = batch.remaining_quantity
        batch.remaining_quantity -= amount
        batch.save()

        InventoryUpdateHistory.objects.create(
            inventory=batch,
            user=request.user,
            field_changed="remaining_quantity",
            old_value=str(old_value),
            new_value=str(batch.remaining_quantity),
        )

        total_stock = product.inventory_batches.filter(status="ACT").aggregate(
            total=Sum("remaining_quantity")
        )["total"] or 0

        trigger_low_stock_notification(product)

        updated_html = render_to_string(
            "products/batch_list.html",
            {"product": product},
            request=request
        )

        return JsonResponse({
            "success": True,
            "total_stock": total_stock,
            "updated_batches_html": updated_html,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@producer_required
@require_POST
def delete_batch(request, pk):
    try:
        # product = Product.objects.get(pk=pk)
        product = get_object_or_404(
                Product,
                pk=pk,
                producer=request.user.producer_profile
            )
        data = json.loads(request.body)

        batch_id = data.get("batch_id")
        # batch = Inventory.objects.get(pk=batch_id, product=product)

        batch = get_object_or_404(
            Inventory,
            pk=batch_id,
            product=product
        )

        # Soft delete
        batch.status = "DEL"
        batch.save()

        # Log history
        InventoryUpdateHistory.objects.create(
            inventory=batch,
            user=request.user,
            field_changed="batch_deleted",
            old_value=str(batch.remaining_quantity),
            new_value="deleted",
        )

        # Recalculate total stock
        total_stock = product.inventory_batches.filter(status="ACT").aggregate(
            total=Sum("remaining_quantity")
        )["total"] or 0

        trigger_low_stock_notification(product)

        updated_html = render_to_string(
            "products/batch_list.html",
            {"product": product},
            request=request
        )

        return JsonResponse({
            "success": True,
            "total_stock": total_stock,
            "updated_batches_html": updated_html,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
    
# TBC remove when background process works
def trigger_low_stock_notification(product):
    total_stock = product.inventory_batches.filter(status="ACT").aggregate(
        total=Sum("remaining_quantity")
    )["total"] or 0

    if total_stock <= product.low_stock_threshold:
        NotificationService.create_unique(
            user=product.producer.user,
            type="PA",
            message=f"Low Stock Alert: { product.name } - only { total_stock } { product.get_unit_display() } remaining.",
            product=product
        )
    else:
        NotificationService.resolve_for_product(product, "PA")