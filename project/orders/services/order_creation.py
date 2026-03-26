from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from orders.models import (
    Order, OrderItem, ProducerOrderSummary, RecurringOrder, RecurringOrderItem
)
from payments.models import Payment
from accounts.models import Address
from carts.services import (
    CartOwner, cart_get_or_create_active, cart_mark_checked_out, _get_effective_unit_price
)
from notifications.models import TraceabilityRecord
import logging
logger = logging.getLogger(__name__)

WHOLESALE_ROLES = {"COMMUNITY_GROUP", "BUSINESS"}

def create_order_from_session(request, validated_data, payment_method, payment_intent_id=None):
    """
    Rebuilds and creates a full Order from:
    - session cart
    - validated checkout form data
    - user or guest info
    - producer-specific delivery/collection fields

    This function is used by:
    - Cash on Delivery checkout
    - Stripe webhook (payment_intent.succeeded)
    """
    try:
        # -----------------------------
        # Resolve user / guest
        # -----------------------------
        if request.user.is_authenticated:
            user = request.user
            is_guest = False
            owner = CartOwner(user_id=user.id)
        else:
            user = None
            is_guest = True

            if not request.session.session_key:
                request.session.create()

            owner = CartOwner(session_key=request.session.session_key)

        wholesale_allowed = False
        if request.user.is_authenticated and request.user.role == "CUSTOMER":
            customer = getattr(request.user, "customer_profile", None)
            if customer and customer.organisation_type:
                wholesale_allowed = customer.organisation_type in WHOLESALE_ROLES

        # -----------------------------
        # Load cart
        # -----------------------------
        cart = cart_get_or_create_active(owner=owner)
        # items = cart.items.select_related("product", "product__producer")
        items = cart.items.select_related(
            "inventory",
            "inventory__product",
            "inventory__product__producer",
        )

        if not items:
            raise ValueError("Cart is empty")

        # -----------------------------
        # Validate stock
        # -----------------------------
        for entry in items:
            product = entry.inventory.product
            quantity = entry.quantity
            inventory = entry.inventory

            if inventory.remaining_quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {inventory.remaining_quantity}, Requested: {quantity}"
                )

        # -----------------------------
        # Extract global fields
        # -----------------------------
        special_instructions = validated_data.get("special_instructions", "")

        # -----------------------------
        # Resolve addresses
        # -----------------------------
        if not is_guest:
            delivery_address = Address.objects.get(id=validated_data["delivery_address_id"])
            billing_address = Address.objects.get(id=validated_data["billing_address_id"])

        else:
            # Guest delivery address
            delivery_address = Address.objects.create(
                user=None,
                line1=validated_data["guest_delivery_line1"],
                line2=validated_data.get("guest_delivery_line2"),
                city=validated_data["guest_delivery_city"],
                postcode=validated_data["guest_delivery_postcode"],
            )

            # Guest billing address
            same_as_delivery = (
                validated_data["guest_billing_line1"] == validated_data["guest_delivery_line1"]
                and validated_data.get("guest_billing_line2") == validated_data.get("guest_delivery_line2")
                and validated_data["guest_billing_city"] == validated_data["guest_delivery_city"]
                and validated_data["guest_billing_postcode"] == validated_data["guest_delivery_postcode"]
            )

            if same_as_delivery:
                billing_address = delivery_address
            else:
                billing_address = Address.objects.create(
                    user=None,
                    line1=validated_data["guest_billing_line1"],
                    line2=validated_data.get("guest_billing_line2"),
                    city=validated_data["guest_billing_city"],
                    postcode=validated_data["guest_billing_postcode"],
                )

        # -----------------------------
        # Create order + items
        # -----------------------------
        with transaction.atomic():

            order = Order.objects.create(
                user=user,
                is_guest=is_guest,
                delivery_address=delivery_address,
                billing_address=billing_address,
                status=Order.Status.PENDING,
                guest_name=validated_data.get("guest_name") if is_guest else None,
                guest_email=validated_data.get("guest_email") if is_guest else None,
                guest_phone=validated_data.get("guest_phone") if is_guest else None,
            )

            total_excl_vat = Decimal("0")
            total_vat = Decimal("0")
            total_discount = Decimal("0")
            commission_total = Decimal("0")

            items_by_producer = {}
            commission_per = Decimal("0.05")

            for entry in items:
                product = entry.inventory.product
                quantity = entry.quantity
                inventory = entry.inventory
                producer = product.producer

                # _get_effective_unit_price returns cheapest price if both wholesale & discount are active
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
                    unit_price = wholesale_tier
                else:
                    unit_price = discounted_price

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
                    inventory=inventory,
                    product=inventory.product,
                    producer=producer,
                    quantity=quantity,
                    original_unit_price=inventory.product.price,
                    final_unit_price=unit_price,
                    vat_amount=vat_amount,
                    vat_rate=vat_rate,
                    commission_amount=commission_amount,
                    discount_amount=discount_amount,
                    preparation_deadline=timezone.now() + timezone.timedelta(hours=48),
                )

                # Create traceability record
                if order.is_guest:
                    TraceabilityRecord.objects.create(
                        order_item=item,
                        inventory=inventory,
                        product=product,
                        producer=producer,
                        guest_name=order.guest_name,
                        guest_email=order.guest_email,
                        guest_phone=order.guest_phone,
                    )
                else:
                    TraceabilityRecord.objects.create(
                        order_item=item,
                        inventory=inventory,
                        product=product,
                        producer=producer,
                        customer=order.user.customer_profile,
                    )

                # Reduce stock
                inventory.remaining_quantity = max(inventory.remaining_quantity - quantity, 0)
                inventory.save(update_fields=["remaining_quantity"])

                items_by_producer.setdefault(product.producer, []).append(item)

            # Update order totals
            order.total_price = total_excl_vat
            order.total_vat = total_vat
            order.total_discount = total_discount
            order.total_commission = commission_total
            order.final_total_price = total_excl_vat + total_vat
            order.save()

            # -----------------------------
            # Producer summaries & Recurring
            # -----------------------------
            for producer, producer_items in items_by_producer.items():

                choice_key = f"delivery_or_collection_{producer.id}"
                date_key = f"delivery_date_{producer.id}"
                time_key = f"delivery_time_{producer.id}"

                delivery_or_collection = validated_data.get(choice_key)
                delivery_date = validated_data.get(date_key)
                delivery_time = validated_data.get(time_key)

                if delivery_or_collection == "DEL":
                    addr = delivery_address
                    addr_line1 = addr.line1
                    addr_line2 = addr.line2
                    addr_city = addr.city
                    addr_postcode = addr.postcode
                else:
                    producer_addr = (
                        producer.user.addresses.filter(is_default_delivery=True).first()
                        or producer.user.addresses.first()
                    )

                    addr_line1 = producer_addr.line1 if producer_addr else producer.farm_name
                    addr_line2 = producer_addr.line2 if producer_addr else ""
                    addr_city = producer_addr.city if producer_addr else ""
                    addr_postcode = producer_addr.postcode if producer_addr else producer.farm_postcode

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
                # Create Recurring Order Template
                # -----------------------------
                is_recurring = validated_data.get(f"is_recurring_{producer.id}")
                recurrence_day = validated_data.get(f"recurrence_day_{producer.id}")

                if (is_recurring == "true" or is_recurring is True) and not is_guest:
                    # Map selected delivery_date to a Day string (e.g. "WED")
                    del_day_str = "WED"
                    if delivery_date:
                        try:
                            dt = datetime.strptime(delivery_date, "%Y-%m-%d")
                            days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                            del_day_str = days[dt.weekday()]
                        except ValueError:
                            pass

                    recurring_template = RecurringOrder.objects.create(
                        user=user,
                        delivery_address=addr if delivery_or_collection == "DEL" else None,
                        recurrence_pattern=RecurringOrder.RecurrencePattern.WEEKLY,
                        recurrence_day=recurrence_day,
                        delivery_day=del_day_str,
                        special_instructions=special_instructions,
                        status=RecurringOrder.Status.ACTIVE
                    )

                    # Add items to the template
                    for item in producer_items:
                        RecurringOrderItem.objects.create(
                            recurring_order=recurring_template,
                            product=item.product,
                            quantity=item.quantity
                        )
                    
                    # Link the initial physical order to this template
                    order.recurring_order = recurring_template
                    order.save(update_fields=['recurring_order'])

            # -----------------------------
            # Payment record
            # -----------------------------
            Payment.objects.create(
                order=order,
                amount=order.final_total_price,
                payment_method=payment_method,
                payment_status=(
                    Payment.Status.SUCCESS if payment_method == "CRD" else Payment.Status.PENDING
                ),
                stripe_payment_intent=payment_intent_id,
            )

            # Clear cart
            cart_mark_checked_out(cart=cart)

        return order
    except Exception as e:
        logger.exception("Order creation failed: %s", e)
        raise