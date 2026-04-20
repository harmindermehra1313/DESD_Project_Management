# added food miles - joe
from django.shortcuts import render, redirect
from django.apps import apps
from decimal import Decimal
from datetime import datetime, timedelta
from carts.services import CartOwner, cart_get_or_create_active, _get_effective_unit_price
from payments.stripe_client import get_stripe
from orders.services.order_creation import create_order_from_session
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
import logging
from django.core.exceptions import ValidationError
from orders.services.session_loader import load_checkout_data_from_session
from orders.services.order_validation import validate_checkout_session
from payments.services import create_payment_intent
from django.urls import reverse
from orders.services.food_miles import calculate_food_miles

Product = apps.get_model('products', 'Product')
Order = apps.get_model('orders', 'Order')
OrderItem = apps.get_model('orders', 'OrderItem')
User = apps.get_model('accounts', 'User')
ProducerOrderSummary = apps.get_model('orders', 'ProducerOrderSummary')
Payment = apps.get_model('payments', 'Payment')
Address = apps.get_model('accounts', 'Address')
stripe = get_stripe()
logger = logging.getLogger(__name__)

WHOLESALE_ROLES = {"COMMUNITY_GROUP", "BUSINESS"}

@require_POST
def checkout_save(request):
    try:
        data = json.loads(request.body)

        request.session["checkout_data"] = data
        request.session.modified = True
        request.session.save()

        return JsonResponse({"ok": True})
    except Exception as e:
        logger.exception("checkout_save failed: %s", e)
        return JsonResponse({"error": "Could not save checkout data"}, status=500)

def checkout_cod(request):
    if request.method != "POST":
        return redirect("orders:checkout")

    session_key = request.session.session_key
    checkout_data = load_checkout_data_from_session(session_key)

    if not checkout_data:
        return redirect("orders:checkout")

    # Validate using same serializer as card payments
    validated_data = validate_checkout_session(checkout_data)

    # Create order using validated data
    order = create_order_from_session(
        request=request,
        validated_data=validated_data,
        payment_method="CSH",
        payment_intent_id=None,
    )

    return redirect("orders:order_success", reference=order.unique_reference)

# def stripe_return(request):
#     try:
#         pi = request.GET.get("payment_intent")

#         if not pi:
#             logger.exception("Stripe return: payment intent does not exist")
#             return redirect("orders:checkout")

#         # Find the order by payment_intent_id
#         try:
#             order = Order.objects.get(payments__stripe_payment_intent=pi)
#             logger.exception("Stripe return order redirect")
#             return redirect("orders:order_success", reference=order.unique_reference)
        
#         except Order.DoesNotExist:
#             logger.warning(f"Stripe return: order does not exist yet for payment intent {pi}")
#             # Show a waiting page that auto-refreshes
#             return render(request, "orders/payment_processing.html", { 
#                 "payment_intent": pi, 
#                 })

#     except Exception as e:
#         logger.exception("Stripe return redirect failed: %s", e)
#         raise

def stripe_return(request):
    try:
        pi = request.GET.get("payment_intent")

        if not pi:
            logger.error("Stripe return: payment intent missing")
            return redirect("orders:checkout")

        is_ajax = request.GET.get("ajax") == "1"

        # Try to find the order
        try:
            order = Order.objects.get(payments__stripe_payment_intent=pi)

            # AJAX polling branch
            if is_ajax:
                return JsonResponse({
                    "status": "succeeded",
                    "redirect_url": reverse("orders:order_success", args=[order.unique_reference])
                })

            # Normal browser redirect
            return redirect("orders:order_success", reference=order.unique_reference)

        except Order.DoesNotExist:
            logger.info(f"Stripe return: order not created yet for PI {pi}")

            # AJAX polling branch
            if is_ajax:
                return JsonResponse({"status": "pending"})

            # First visit, show processing page
            return render(request, "orders/payment_processing.html", {
                "payment_intent": pi,
            })

    except Exception as e:
        logger.exception("Stripe return failed: %s", e)
        raise


def checkout(request):
    # Check for payment timeout
    timeout_flag = request.GET.get("timeout") == "1"
    timed_out_pi = request.GET.get("pi")

    # Get cart
    if request.user.is_authenticated:
        owner = CartOwner(user_id=request.user.id)
    else:
        if not request.session.session_key:
            request.session.create()
            request.session.save()
        owner = CartOwner(session_key=request.session.session_key)
    
    # Wholesale pricing check
    wholesale_allowed = False
    if request.user.is_authenticated and request.user.role == "CUSTOMER":
        customer = getattr(request.user, "customer_profile", None)
        if customer and customer.organisation_type:
            wholesale_allowed = customer.organisation_type in WHOLESALE_ROLES

    cart = cart_get_or_create_active(owner=owner)
    # items = cart.items.select_related("product", "product__producer")
    items = cart.items.select_related(
        "inventory",
        "inventory__product",
        "inventory__product__producer",
    )

    # Logged-in user: load real addresses
    if request.user.is_authenticated:
        user = request.user
        addresses = user.addresses.all()

        default_address = (
            addresses.filter(is_default_delivery=True).first()
            or addresses.first()
        )

        default_billing = (
            addresses.filter(is_default_billing=True).first()
            or addresses.first()
        )

    # Guest user: no saved addresses
    else:
        user = None
        addresses = []
        default_address = None
        default_billing = None

    customer_postcode = default_address.postcode if default_address else None
    food_miles_cache = {}

    enriched_items = []
    producers = {}
    total = Decimal("0")
    vat_cart_total = Decimal("0")
    order_savings_total = Decimal("0")
    total_food_miles = None
    counted_food_miles_producer_ids = set()

    for entry in items:
        # product = Product.objects.get(id=entry["product_id"])
        # quantity = entry["quantity"]
        # product = entry.product
        product = entry.inventory.product
        inventory = entry.inventory
        quantity = entry.quantity
        producer = product.producer

        food_miles_cache_key = (producer.farm_postcode, customer_postcode)
        if food_miles_cache_key in food_miles_cache:
            food_miles = food_miles_cache[food_miles_cache_key]
        else:
            food_miles = calculate_food_miles(producer.farm_postcode, customer_postcode)
            food_miles_cache[food_miles_cache_key] = food_miles

        line_food_miles = food_miles
        if food_miles is not None and producer.id not in counted_food_miles_producer_ids:
            counted_food_miles_producer_ids.add(producer.id)
            if total_food_miles is None:
                total_food_miles = Decimal("0.00")
            total_food_miles += food_miles
        
        # Price
        #discounted_price = inventory.get_discounted_price() # Normal price if no discount
        # discounted_price = _get_effective_unit_price(
        #     inventory_id=inventory.id,
        #     qty=1,   # discounted price per unit
        # )
        # wholesale_tier = product.get_wholesale_price(quantity) # None if no wholesale
        # # unit_price = wholesale_tier or discounted_price
        # unit_price = _get_effective_unit_price(
        #     inventory_id=inventory.id,
        #     qty=quantity,
        # )

        # Base discounted price (retail discounts only)
        discounted_price = _get_effective_unit_price(
            inventory_id=inventory.id,
            qty=1,
        )

        # Wholesale tier (if any)
        wholesale_tier = product.get_wholesale_price(quantity)

        # Determine final unit price
        if wholesale_allowed and wholesale_tier:
            # Wholesale applies
            unit_price = wholesale_tier
            is_wholesale = True
        else:
            # Retail only (even if wholesale tier exists)
            unit_price = discounted_price
            is_wholesale = False

        
        # VAT
        vat_rate = product.category.vat
        vat_fraction = vat_rate / Decimal('100')
        vat_per_unit = unit_price * vat_fraction
        vat_total = vat_per_unit * quantity
        vat_cart_total += vat_total
        
        # Total price
        total_price = unit_price * quantity

        # Savings
        savings_per_unit = product.price - unit_price
        savings_total = savings_per_unit * quantity

        # savings per order
        order_savings_total += savings_total

        enriched_item = {
            "product": product,
            "inventory": inventory,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "vat_per_unit": vat_per_unit,
            "vat_total": vat_total,
            "vat_rate": vat_rate,
            "is_discounted": discounted_price != product.price,
            "is_wholesale": is_wholesale,
            "original_price": product.price,
            "discounted_price": discounted_price,
            "savings_per_unit": savings_per_unit,
            "savings_total": savings_total,
            "producer": producer,
            "food_miles": food_miles,
            "line_food_miles": line_food_miles,
        }

        total += total_price
        enriched_items.append(enriched_item)

        # Group by producer
        if producer not in producers:
            # producers[producer] = []
            producers[producer] = {
                "items": [],
                "subtotal": Decimal("0"),
                "vat_total": Decimal("0"),
                "savings_total": Decimal("0"),
                "grand_total": Decimal("0"),
                "expiry_dates": [],
                "food_miles_total": None,
            }
        
        #producers[producer].append(enriched_item)
        producers[producer]["items"].append(enriched_item)

        # Store expiry dates for max date calculation
        # if product.expiry_date:
            # producers[producer]["expiry_dates"].append(product.expiry_date)
        if inventory.expiry_date:
            producers[producer]["expiry_dates"].append(inventory.expiry_date)
    
        # Get subtotals for each producer
        producers[producer]["subtotal"] += product.price * quantity
        producers[producer]["vat_total"] += vat_total
        producers[producer]["savings_total"] += savings_total
        producers[producer]["grand_total"] += total_price + vat_total
        if line_food_miles is not None and producers[producer]["food_miles_total"] is None:
            producers[producer]["food_miles_total"] = line_food_miles

        # TBC Get producers address as collection address??
        producer_address = producer.user.addresses.first()

        # Store address for collection notice
        producers[producer]["collection_address"] = {
            "producer_id": producer.id,
            "farm_name": producer.farm_name,
            "producer_name": producer.user.name,
            "line1": producer_address.line1 if producer_address else producer.farm_name,
            "line2": producer_address.line2 if producer_address else "",
            "city": producer_address.city if producer_address else "",
            "postcode": producer_address.postcode if producer_address else producer.farm_postcode,
        }
    
    # Build flat list of all possible collection addresses
    collection_addresses = [
        data["collection_address"]
        for data in producers.values()
    ]

    # Get maximum date for each producer
    # max is 2 days before shortest product expiry
    for producer, data in producers.items():
        expiry_dates = data.get("expiry_dates", [])

        if expiry_dates:
            earliest_expiry = min(expiry_dates)
            max_delivery_date = earliest_expiry - timedelta(days=2)
        else:
            max_delivery_date = None

        data["max_delivery_date"] = max_delivery_date

    # Get original total before vat or discounts
    original_total = total + order_savings_total

    # Dates for date validation
    now = datetime.now()
    collection_earliest = now + timedelta(hours=48)
    delivery_earliest = now + timedelta(hours=72)

    def round_up_to_next_slot(dt, slot_hours):
        """
        dt: datetime
        slot_hours: list of integers representing slot start hours (e.g. [9, 11, 13, 15])
        """
        minutes = dt.hour * 60 + dt.minute
        slot_minutes = [h * 60 for h in slot_hours]

        # Find the next slot today
        for sm in slot_minutes:
            if sm >= minutes:
                return dt.replace(
                    hour=sm // 60,
                    minute=0,
                    second=0,
                    microsecond=0
                )

        # If no slot left today, next day at first slot
        first = slot_minutes[0]
        next_day = dt + timedelta(days=1)
        return next_day.replace(
            hour=first // 60,
            minute=0,
            second=0,
            microsecond=0
        )

    # Round collection earliest to next valid slot
    collection_earliest = round_up_to_next_slot(
        collection_earliest,
        slot_hours=[9, 11, 13, 15]   # collection slots
    )

    # Round delivery earliest to next valid slot
    delivery_earliest = round_up_to_next_slot(
        delivery_earliest,
        slot_hours=[10, 12, 14, 16]  # delivery slots
    )

    amount = total + vat_cart_total

    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None

    try:
        intent = create_payment_intent(amount, session_key=session_key, user_id=user_id)
        client_secret = intent.client_secret
    except ValidationError:
        client_secret = None  # too small, no intent created

    context = {
        "cart": {
            "items": enriched_items,
            "total": total,
            "vat_total": vat_cart_total,
            "savings_total": order_savings_total,
            "original_total": original_total,
            "final_total": total + vat_cart_total,
            "total_food_miles": total_food_miles,
        },
        "addresses": addresses,
        "default_delivery": default_address,
        "default_billing": default_billing,
        "collection_earliest": collection_earliest,
        "delivery_earliest": delivery_earliest,
        "producers": producers,
        "collection_addresses": collection_addresses,
        "client_secret": client_secret,
        "STRIPE_PUBLISHABLE_KEY": settings.STRIPE_PUBLIC_KEY,
        "payment_timeout": timeout_flag,
        "timed_out_pi": timed_out_pi,
    }

    return render(request, "orders/checkout.html", context)

def order_success(request, reference):
    order = Order.objects.get(unique_reference=reference)

    # Fetch producer summaries
    producer_summaries = (
        order.producer_summaries
        .select_related("producer")
        .all()
    )

    # Group items by producer
    items_by_producer = {}
    for item in order.items.select_related("producer", "product"):
        # Line total after discount, before VAT
        item.line_total = item.final_unit_price * item.quantity
        items_by_producer.setdefault(item.producer_id, []).append(item)

    # Recalc monetary values from items
    for summary in producer_summaries:
        items = items_by_producer.get(summary.producer_id, [])
        summary.items = items

        # Total (no discounts/wholesale)
        summary.original_subtotal = sum( 
            item.original_unit_price * item.quantity for item in items
        )

        # Subtotal (after discount, before VAT)
        summary.discounted_subtotal = sum(
            item.final_unit_price * item.quantity for item in items
        )

        # Total discount (difference between original and final)
        summary.discount_total = summary.original_subtotal - summary.discounted_subtotal

        # VAT
        summary.vat_total = sum(
            item.vat_amount for item in items
        )

        # What the customer paid for this producer
        summary.customer_paid = summary.discounted_subtotal + summary.vat_total

        # Commission (per item)
        summary.commission_total = sum(
            item.commission_amount for item in items
        )

        # What the producer receives
        summary.payout_amount = summary.discounted_subtotal - summary.commission_total

    return render(request, "orders/order_confirmed.html", {
        "order": order,
        "producer_summaries": producer_summaries,
    })
