from django.shortcuts import render, redirect
from django.apps import apps
from decimal import Decimal
from datetime import datetime, timedelta, time
from django.utils import timezone
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status
from django.db import transaction
from orders.serializers.checkout import CheckoutSerializer
from carts.services import CartOwner, cart_get_or_create_active, cart_merge_guest_into_user, cart_mark_checked_out

Product = apps.get_model('products', 'Product')
Order = apps.get_model('orders', 'Order')
OrderItem = apps.get_model('orders', 'OrderItem')
User = apps.get_model('accounts', 'User')
ProducerOrderSummary = apps.get_model('orders', 'ProducerOrderSummary')
Payment = apps.get_model('payments', 'Payment')
Address = apps.get_model('accounts', 'Address')

class CheckoutAPIView(APIView):
    def post(self, request):
        # Get user either guest or logged in
        if request.user.is_authenticated:
            user = request.user
            is_guest = False
        else:
            user = None
            is_guest = True

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # cart = request.session.get("cart", {})
        # items = cart.get("items", [])
        if request.user.is_authenticated:
            owner = CartOwner(user_id=request.user.id)
        else:
            if not request.session.session_key:
                request.session.create()
            owner = CartOwner(session_key=request.session.session_key)
        
        cart = cart_get_or_create_active(owner=owner)
        items = cart.items.select_related("product", "product__producer")

        if not items:
            return Response(
                {"error": "Cart is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # -----------------------------
        # Validate stock for each item
        # -----------------------------
        for entry in items:
            # product = Product.objects.get(id=entry["product_id"])
            # quantity = entry["quantity"]
            product = entry.product
            quantity = entry.quantity

            if product.stock_quantity < quantity:
                return Response(
                    {
                        "error": f"Insufficient stock for {product.name}. "
                                f"Available: {product.stock_quantity}, "
                                f"Requested: {quantity}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )


        # -----------------------------
        # Extract global checkout fields
        # -----------------------------
        #delivery_address_id = serializer.validated_data["delivery_address_id"]
        #delivery_address = Address.objects.get(id=delivery_address_id)

        payment_method = serializer.validated_data["payment_method"]
        special_instructions = serializer.validated_data.get("special_instructions", "")

        # -----------------------------
        # Resolve delivery & billing address
        # -----------------------------

        if not is_guest:
            # Logged-in user: use saved addresses
            delivery_address_id = serializer.validated_data["delivery_address_id"]
            delivery_address = Address.objects.get(id=delivery_address_id)
            
            billing_address_id = serializer.validated_data.get("billing_address_id")
            billing_address = Address.objects.get(id=billing_address_id)
        
        else:
            # Guest: create delivery & billing addresses
            delivery_address = Address.objects.create(
                user = None,
                line1 = serializer.validated_data["guest_delivery_line1"],
                line2 = serializer.validated_data.get("guest_delivery_line2"),
                city = serializer.validated_data["guest_delivery_city"],
                postcode = serializer.validated_data["guest_delivery_postcode"],
            )
            
            # Check if billing = delivery (store once)
            same_as_delivery = (
                serializer.validated_data["guest_billing_line1"] == serializer.validated_data["guest_delivery_line1"] and
                serializer.validated_data.get("guest_billing_line2") == serializer.validated_data.get("guest_delivery_line2") and
                serializer.validated_data["guest_billing_city"] == serializer.validated_data["guest_delivery_city"]
                and serializer.validated_data["guest_billing_postcode"] == serializer.validated_data["guest_delivery_postcode"]
            )

            if same_as_delivery:
                billing_address = delivery_address
            else:        
                billing_address = Address.objects.create(
                    user = None,
                    line1 = serializer.validated_data["guest_billing_line1"],
                    line2 = serializer.validated_data.get("guest_billing_line2"),
                    city = serializer.validated_data["guest_billing_city"],
                    postcode = serializer.validated_data["guest_billing_postcode"],
                )

        # -----------------------------
        # Get dynamic producer fields
        # -----------------------------

        with transaction.atomic():

            # -----------------------------
            # Create order (global)
            # -----------------------------
            order = Order.objects.create(
                user=user,
                is_guest=is_guest,
                delivery_address=delivery_address,
                billing_address=billing_address,
                status=Order.Status.PENDING,
                guest_name=serializer.validated_data.get("guest_name") if is_guest else None,
                guest_email=serializer.validated_data.get("guest_email") if is_guest else None,
                guest_phone=serializer.validated_data.get("guest_phone") if is_guest else None,
            )

            # -----------------------------
            # Create order items
            # -----------------------------
            total_excl_vat = Decimal("0")
            total_vat = Decimal("0")
            total_discount = Decimal("0")
            commission_total = Decimal("0")

            items_by_producer = {}
            commission_per = Decimal("0.05")

            for entry in items:
                # product = Product.objects.get(id=entry["product_id"])
                # quantity = entry["quantity"]
                product = entry.product
                quantity = entry.quantity

                # Pricing logic
                discounted_price = product.get_discounted_price()
                wholesale_tier = product.get_wholesale_price(quantity)
                unit_price = wholesale_tier or discounted_price

                original_unit_price = product.price
                original_line_total = original_unit_price * quantity

                line_total = unit_price * quantity
                discount_amount = original_line_total - line_total

                vat_rate = product.category.vat
                vat_fraction = vat_rate / Decimal("100")
                vat_per_unit = unit_price * vat_fraction
                vat_amount = vat_per_unit * quantity

                commission_amount = line_total * commission_per

                total_excl_vat += line_total
                total_vat += vat_amount
                total_discount += discount_amount
                commission_total += commission_amount

                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    producer=product.producer,
                    quantity=quantity,
                    original_unit_price=original_unit_price,
                    final_unit_price=unit_price,
                    vat_amount=vat_amount,
                    vat_rate=vat_rate,
                    commission_amount=commission_amount,
                    discount_amount=discount_amount,
                    preparation_deadline=timezone.now() + timedelta(hours=48),
                )

                # Reduce stock
                product.stock_quantity = max(product.stock_quantity - quantity, 0)
                product.save(update_fields=["stock_quantity"])

                items_by_producer.setdefault(product.producer, []).append(item)

            # Update order totals
            order.total_price = total_excl_vat
            order.total_vat = total_vat
            order.total_discount = total_discount
            order.total_commission = commission_total
            order.final_total_price = total_excl_vat + total_vat
            order.save()

            # -----------------------------
            # Create ProducerOrderSummary for each producer
            # -----------------------------
            for producer, producer_items in items_by_producer.items():

                # Extract producer-specific fields
                choice_key = f"delivery_or_collection_{producer.id}"
                date_key = f"delivery_date_{producer.id}"
                time_key = f"delivery_time_{producer.id}"

                delivery_or_collection = serializer.validated_data.get(choice_key)
                delivery_date = serializer.validated_data.get(date_key)
                delivery_time = serializer.validated_data.get(time_key)

                # Resolve the actual address used
                if delivery_or_collection == "DEL":
                    # Use the order's delivery address
                    addr = delivery_address
                    addr_line1 = addr.line1
                    addr_line2 = addr.line2
                    addr_city = addr.city
                    addr_postcode = addr.postcode

                else:
                    # TBC Use producer farm address (fallback to user address if needed)
                    producer_addr = (
                        producer.user.addresses.filter(is_default_delivery=True).first()
                        or producer.user.addresses.first()
                    )

                    addr_line1 = producer_addr.line1 if producer_addr else producer.farm_name
                    addr_line2 = producer_addr.line2 if producer_addr else ""
                    addr_city = producer_addr.city if producer_addr else ""
                    addr_postcode = producer_addr.postcode if producer_addr else producer.farm_postcode

                # Totals
                subtotal = sum(i.final_unit_price * i.quantity for i in producer_items)
                vat_total_p = sum(i.vat_amount for i in producer_items)
                commission_total_p = sum(i.commission_amount for i in producer_items)
                payout_amount = subtotal - commission_total_p

                ProducerOrderSummary.objects.create(
                    order=order,
                    producer=producer,
                    subtotal=subtotal,
                    vat_total=vat_total_p,
                    commission_total=commission_total_p,
                    payout_amount=payout_amount,
                    delivery_date=delivery_date,
                    special_instructions=special_instructions,
                    status=ProducerOrderSummary.Status.PENDING,
                    delivery_or_collection=delivery_or_collection,
                    delivery_time_slot=delivery_time,
                    address_line1=addr_line1,
                    address_line2=addr_line2,
                    city=addr_city,
                    postcode=addr_postcode,
                )

            # -----------------------------
            # Create payment record
            # -----------------------------
            Payment.objects.create(
                order=order,
                amount=order.final_total_price,
                payment_method=payment_method,
                payment_status=Payment.Status.PENDING,
                sandbox_mode=True,
            )

            # Clear cart
            #request.session["cart"] = {"items": []}
            cart = cart_mark_checked_out(cart=cart)

        return Response(
            {
                "order_id": order.id,
                "unique_reference": order.unique_reference
            },
            status=status.HTTP_201_CREATED
        )
    
def fake_add_to_cart(request):
    # TBC Temporary cart structure with multiple items
    products = Product.objects.all()[:3]

    request.session["cart"] = {
        "items": [
            {"product_id": products[0].id, "quantity": 100},
            {"product_id": products[1].id, "quantity": 2},
            {"product_id": products[2].id, "quantity": 5},
        ]
    }

    return redirect("orders:checkout")

def checkout(request):
    # Get cart
    # cart = request.session.get("cart", {})
    # items = cart.get("items", [])
    if request.user.is_authenticated:
        owner = CartOwner(user_id=request.user.id)
    else:
        if not request.session.session_key:
            request.session.create()
        owner = CartOwner(session_key=request.session.session_key)
    
    cart = cart_get_or_create_active(owner=owner)
    items = cart.items.select_related("product", "product__producer")

    enriched_items = []
    producers = {}
    total = Decimal("0")
    vat_cart_total = Decimal("0")
    order_savings_total = Decimal("0")

    for entry in items:
        # product = Product.objects.get(id=entry["product_id"])
        # quantity = entry["quantity"]
        product = entry.product
        quantity = entry.quantity
        producer = product.producer
        
        # Price
        discounted_price = product.get_discounted_price() # Normal price if no discount
        wholesale_tier = product.get_wholesale_price(quantity) # None if no wholesale
        unit_price = wholesale_tier or discounted_price
        
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
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "vat_per_unit": vat_per_unit,
            "vat_total": vat_total,
            "vat_rate": vat_rate,
            "is_discounted": discounted_price != product.price,
            "is_wholesale": wholesale_tier is not None,
            "original_price": product.price,
            "discounted_price": discounted_price,
            "savings_per_unit": savings_per_unit,
            "savings_total": savings_total,
            "producer": producer,
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
            }
        
        #producers[producer].append(enriched_item)
        producers[producer]["items"].append(enriched_item)
    
        # Get subtotals for each producer
        producers[producer]["subtotal"] += product.price * quantity
        producers[producer]["vat_total"] += vat_total
        producers[producer]["savings_total"] += savings_total
        producers[producer]["grand_total"] += total_price + vat_total

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

    # Get original total before vat or discounts
    original_total = total + order_savings_total

    # Logged‑in user: load real addresses
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

    context = {
        "cart": {
            "items": enriched_items,
            "total": total,
            "vat_total": vat_cart_total,
            "savings_total": order_savings_total,
            "original_total": original_total,
            "final_total": total + vat_cart_total,
        },
        "addresses": addresses,
        "default_delivery": default_address,
        "default_billing": default_billing,
        "collection_earliest": collection_earliest,
        "delivery_earliest": delivery_earliest,
        "producers": producers,
        "collection_addresses": collection_addresses,
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
