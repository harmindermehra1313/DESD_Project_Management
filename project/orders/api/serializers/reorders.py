"""
orders/api/serializers/reorders.py

Purpose:
Define API serializers for order history, order detail, reorder responses,
and reorder request payloads.
"""

from __future__ import annotations

from rest_framework import serializers

from orders.models import Order, OrderItem, ProducerOrderSummary
from orders.selectors import get_derived_order_status_label
from reviews.models import Review
from reviews.selectors import (
    build_review_action_for_order_item,
    get_reviewed_product_ids_for_user_and_products,
)
from orders.services.order_status import get_order_status_context
from decimal import Decimal, ROUND_HALF_UP

MONEY_PLACES = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _active_quantity(item: OrderItem) -> int:
    return max(int(item.quantity or 0) - int(item.cancelled_quantity or 0), 0)


def _cancelled_quantity(item: OrderItem) -> int:
    return max(int(item.cancelled_quantity or 0), 0)


def _vat_per_unit(item: OrderItem) -> Decimal:
    if not item.quantity or item.quantity <= 0:
        return Decimal("0.00")

    return _money(Decimal(item.vat_amount or 0) / Decimal(item.quantity))


def _line_total_for_quantity(item: OrderItem, quantity: int) -> Decimal:
    quantity = Decimal(quantity)
    unit_price = Decimal(item.final_unit_price or 0)
    vat_per_unit = _vat_per_unit(item)

    return _money((unit_price + vat_per_unit) * quantity)


def _active_order_total(order: Order) -> Decimal:
    total = Decimal("0.00")

    for item in order.items.all():
        total += _line_total_for_quantity(item, _active_quantity(item))

    return _money(total)


def _cancelled_order_total(order: Order) -> Decimal:
    total = Decimal("0.00")

    for item in order.items.all():
        total += _line_total_for_quantity(item, _cancelled_quantity(item))

    return _money(total)


def _has_cancelled_quantities(order: Order) -> bool:
    return any(
        int(getattr(item, "cancelled_quantity", 0) or 0) > 0
        for item in order.items.all()
    )


def _is_cash_payment_display(payment_method_display: str | None) -> bool:
    return "cash" in str(payment_method_display or "").lower()


class OrderHistorySerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="unique_reference", read_only=True)
    order_status = serializers.SerializerMethodField()
    order_status_code = serializers.SerializerMethodField()
    order_status_key = serializers.SerializerMethodField()
    is_partially_cancelled = serializers.SerializerMethodField()
    can_customer_cancel = serializers.SerializerMethodField()
    status_note = serializers.SerializerMethodField()

    total = serializers.SerializerMethodField()
    original_total_price = serializers.DecimalField(
        source="total_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    active_total_price = serializers.SerializerMethodField()
    cancelled_total_price = serializers.SerializerMethodField()
    producer_names = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "total",
            "original_total_price",
            "active_total_price",
            "cancelled_total_price",
            "order_status",
            "order_status_code",
            "order_status_key",
            "is_partially_cancelled",
            "can_customer_cancel",
            "status_note",
            "producer_names",
        ]

    def _status_context(self, obj: Order) -> dict:
        return get_order_status_context(obj)

    def get_order_status(self, obj: Order) -> str:
        return self._status_context(obj)["status_display"]

    def get_order_status_code(self, obj: Order) -> str:
        return self._status_context(obj)["status_code"]

    def get_order_status_key(self, obj: Order) -> str:
        return self._status_context(obj)["status_key"]

    def get_is_partially_cancelled(self, obj: Order) -> bool:
        return self._status_context(obj)["is_partially_cancelled"]

    def get_can_customer_cancel(self, obj: Order) -> bool:
        return self._status_context(obj)["can_customer_cancel"]

    def get_producer_names(self, obj: Order) -> list[str]:
        names: list[str] = []

        for summary in obj.producer_summaries.all():
            producer_name = getattr(summary.producer, "farm_name", None)
            if producer_name and producer_name not in names:
                names.append(producer_name)

        return names

    def get_total(self, obj: Order) -> Decimal:
        if _has_cancelled_quantities(obj):
            return _active_order_total(obj)

        return obj.total_price

    def get_active_total_price(self, obj: Order) -> Decimal:
        return _active_order_total(obj)

    def get_cancelled_total_price(self, obj: Order) -> Decimal:
        return _cancelled_order_total(obj)

    def get_status_note(self, obj: Order) -> str:
        if self._status_context(obj)["is_partially_cancelled"]:
            return "Some quantities were cancelled. The order total reflects the active items only."
        return ""


class OrderItemDetailSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    paid_unit_price = serializers.DecimalField(
        source="final_unit_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    producer = serializers.SerializerMethodField()
    review_action = serializers.SerializerMethodField()

    status = serializers.SerializerMethodField()
    status_key = serializers.SerializerMethodField()
    cancelled_quantity = serializers.IntegerField(read_only=True)
    active_quantity = serializers.SerializerMethodField()
    can_customer_cancel_item = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "quantity",
            "active_quantity",
            "cancelled_quantity",
            "status",
            "status_key",
            "can_customer_cancel_item",
            "paid_unit_price",
            "producer",
            "review_action",
        ]

    def get_product_name(self, obj: OrderItem) -> str:
        snapshot_name = getattr(obj, "product_name_snapshot", None)
        if snapshot_name:
            return snapshot_name

        if obj.product_id and obj.product:
            return obj.product.name

        return "Unknown product"

    def get_producer(self, obj: OrderItem) -> str:
        snapshot_name = getattr(obj, "producer_name_snapshot", None)
        if snapshot_name:
            return snapshot_name

        if obj.producer_id and obj.producer:
            producer_name = getattr(obj.producer, "farm_name", None)
            if producer_name:
                return producer_name
            return str(obj.producer)

        return "Unknown producer"

    def get_review_action(self, obj: OrderItem) -> dict:
        request = self.context.get("request")
        reviewed_product_ids = self.context.get("reviewed_product_ids", set())
        user_id = getattr(getattr(request, "user", None), "id", None)

        return build_review_action_for_order_item(
            order_item=obj,
            user_id=user_id,
            reviewed_product_ids=reviewed_product_ids,
        )

    def get_status(self, obj: OrderItem) -> str:
        return obj.get_status_display()

    def get_status_key(self, obj: OrderItem) -> str:
        return str(obj.status).lower()

    def get_active_quantity(self, obj: OrderItem) -> int:
        return max(obj.quantity - obj.cancelled_quantity, 0)

    def get_can_customer_cancel_item(self, obj: OrderItem) -> bool:
        if obj.status == OrderItem.Status.CANCELLED:
            return False

        order = obj.order

        if order.status in {
            Order.Status.CANCELLED,
            Order.Status.COMPLETED,
        }:
            return False

        producer_summary = (
            order.producer_summaries.filter(producer_id=obj.producer_id)
            .order_by("id")
            .first()
        )

        if producer_summary is None:
            return False

        return producer_summary.status == ProducerOrderSummary.Status.PENDING


class ProducerOrderSummarySerializer(serializers.ModelSerializer):
    producer_name = serializers.CharField(source="producer.farm_name", read_only=True)
    status = serializers.CharField(source="get_status_display", read_only=True)
    delivery_or_collection = serializers.CharField(
        source="get_delivery_or_collection_display",
        read_only=True,
    )
    delivery_date = serializers.SerializerMethodField()
    collection_date = serializers.SerializerMethodField()
    delivery_time_slot = serializers.SerializerMethodField()
    collection_time_slot = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    collection_address = serializers.SerializerMethodField()

    class Meta:
        model = ProducerOrderSummary
        fields = [
            "id",
            "producer_id",
            "producer_name",
            "status",
            "delivery_or_collection",
            "delivery_date",
            "collection_date",
            "delivery_time_slot",
            "collection_time_slot",
            "delivery_address",
            "collection_address",
            "subtotal",
            "vat_total",
            "special_instructions",
        ]

    def _build_address_payload(self, obj: ProducerOrderSummary) -> dict | None:
        if not any([obj.address_line1, obj.address_line2, obj.city, obj.postcode]):
            return None

        return {
            "line_1": obj.address_line1,
            "line_2": obj.address_line2,
            "city": obj.city,
            "postcode": obj.postcode,
        }

    def get_delivery_date(self, obj: ProducerOrderSummary):
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return obj.delivery_date
        return None

    def get_collection_date(self, obj: ProducerOrderSummary):
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return obj.delivery_date
        return None

    def get_delivery_time_slot(self, obj: ProducerOrderSummary):
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return obj.delivery_time_slot
        return None

    def get_collection_time_slot(self, obj: ProducerOrderSummary):
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return obj.delivery_time_slot
        return None

    def get_delivery_address(self, obj: ProducerOrderSummary) -> dict | None:
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return self._build_address_payload(obj)
        return None

    def get_collection_address(self, obj: ProducerOrderSummary) -> dict | None:
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return self._build_address_payload(obj)
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="unique_reference", read_only=True)
    items = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    producer_breakdown = ProducerOrderSummarySerializer(
        source="producer_summaries",
        many=True,
        read_only=True,
    )
    payment_method_display = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    status_code = serializers.SerializerMethodField()
    status_key = serializers.SerializerMethodField()
    is_partially_cancelled = serializers.SerializerMethodField()
    can_customer_cancel = serializers.SerializerMethodField()
    status_note = serializers.SerializerMethodField()
    original_total_price = serializers.DecimalField(
        source="total_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    active_total_price = serializers.SerializerMethodField()
    cancelled_total_price = serializers.SerializerMethodField()
    display_total_price = serializers.SerializerMethodField()
    display_total_label = serializers.SerializerMethodField()
    display_total_note = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "original_total_price",
            "active_total_price",
            "cancelled_total_price",
            "display_total_price",
            "display_total_label",
            "display_total_note",
            "status",
            "status_code",
            "status_key",
            "is_partially_cancelled",
            "can_customer_cancel",
            "status_note",
            "items",
            "producer_breakdown",
            "payment_method_display",
            "total_price",
        ]

    def get_items(self, obj: Order) -> list[dict]:
        request = self.context.get("request")
        user_id = getattr(getattr(request, "user", None), "id", None)

        product_ids = list(
            obj.items.exclude(product_id__isnull=True).values_list(
                "product_id", flat=True
            )
        )

        reviewed_product_ids = get_reviewed_product_ids_for_user_and_products(
            user_id=user_id,
            product_ids=product_ids,
        )

        serializer = OrderItemDetailSerializer(
            obj.items.all(),
            many=True,
            read_only=True,
            context={
                **self.context,
                "reviewed_product_ids": reviewed_product_ids,
            },
        )
        return serializer.data

    def _status_context(self, obj: Order) -> dict:
        return get_order_status_context(obj)

    def get_status(self, obj: Order) -> str:
        return self._status_context(obj)["status_display"]

    def get_active_total_price(self, obj: Order) -> Decimal:
        return _active_order_total(obj)

    def get_cancelled_total_price(self, obj: Order) -> Decimal:
        return _cancelled_order_total(obj)

    def get_display_total_price(self, obj: Order) -> Decimal:
        if _has_cancelled_quantities(obj):
            return _active_order_total(obj)

        return obj.total_price

    def get_display_total_label(self, obj: Order) -> str:
        payment_display = self.get_payment_method_display(obj)
        has_cancellations = _has_cancelled_quantities(obj)

        if _is_cash_payment_display(payment_display):
            return "Amount due at collection"

        if has_cancellations:
            return "Total after cancellations"

        return "Total paid"

    def get_display_total_note(self, obj: Order) -> str:
        payment_display = self.get_payment_method_display(obj)

        if not _has_cancelled_quantities(obj):
            return ""

        if _is_cash_payment_display(payment_display):
            return "Cancelled value has been removed from the amount due at collection."

        return "Cancelled value has been removed from the active order total."

    def get_status_code(self, obj: Order) -> str:
        return self._status_context(obj)["status_code"]

    def get_status_key(self, obj: Order) -> str:
        return self._status_context(obj)["status_key"]

    def get_is_partially_cancelled(self, obj: Order) -> bool:
        return self._status_context(obj)["is_partially_cancelled"]

    def get_can_customer_cancel(self, obj: Order) -> bool:
        return self._status_context(obj)["can_customer_cancel"]

    def get_status_note(self, obj: Order) -> str:
        if self._status_context(obj)["is_partially_cancelled"]:
            return "Some quantities were cancelled. The order total below reflects active items only."
        return ""

    def get_payment_method_display(self, obj: Order) -> str | None:
        payments = list(obj.payments.all().order_by("-created_at"))

        if not payments:
            return None

        successful_payment = next(
            (
                payment
                for payment in payments
                if payment.payment_status == payment.Status.SUCCESS
            ),
            None,
        )
        payment = successful_payment or payments[0]

        if payment.payment_method == payment.Method.CARD:
            last4 = getattr(obj, "payment_last4", None)
            if last4:
                return f"**** **** **** {last4}"

        return payment.get_payment_method_display()


class ReorderWholesaleTierSerializer(serializers.Serializer):
    min_quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReorderPricingSurplusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    discount_percentage = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    discounted_unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


class ReorderPricingWholesaleSerializer(serializers.Serializer):
    has_wholesale_tiers = serializers.BooleanField()
    active_for_quantity = serializers.BooleanField()
    evaluated_quantity = serializers.IntegerField()
    matched_tier = ReorderWholesaleTierSerializer(required=False, allow_null=True)
    next_tier = ReorderWholesaleTierSerializer(required=False, allow_null=True)


class ReorderPricingSerializer(serializers.Serializer):
    base_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    pricing_source = serializers.CharField()
    surplus = ReorderPricingSurplusSerializer()
    wholesale = ReorderPricingWholesaleSerializer()


class ReorderSuggestedItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    inventory_id = serializers.IntegerField()
    available_quantity = serializers.IntegerField()
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    pricing = ReorderPricingSerializer()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    product_type_id = serializers.IntegerField(required=False, allow_null=True)
    product_type_name = serializers.CharField(required=False, allow_null=True)
    match_basis = serializers.CharField()
    recommendation_badge = serializers.CharField(required=False, allow_blank=True)


class ReorderUnavailableItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    reason = serializers.CharField()
    reason_code = serializers.CharField(required=False, allow_blank=True)
    reason_data = serializers.DictField(required=False)
    producer_id = serializers.IntegerField(required=False)
    producer_name = serializers.CharField(required=False)
    suggested_items = ReorderSuggestedItemSerializer(many=True, required=False)


class ReorderQuantityAdjustedItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    reason = serializers.CharField()
    reason_code = serializers.CharField(required=False, allow_blank=True)
    reason_data = serializers.DictField(required=False)


class ReorderPriceChangedItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    pricing_source = serializers.CharField(required=False)
    surplus_active = serializers.BooleanField(required=False)
    wholesale_active_for_quantity = serializers.BooleanField(required=False)

    producer_changed = serializers.BooleanField(required=False)
    original_producer_id = serializers.IntegerField(required=False)
    original_producer_name = serializers.CharField(required=False)
    current_producer_id = serializers.IntegerField(required=False)
    current_producer_name = serializers.CharField(required=False)
    message = serializers.CharField(required=False)


class ReorderAddedItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    inventory_id = serializers.IntegerField()


class ReorderAddableItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    inventory_id = serializers.IntegerField(required=False)
    available_quantity = serializers.IntegerField(required=False)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    pricing = ReorderPricingSerializer()
    match_basis = serializers.CharField(required=False)
    suggested_items = ReorderSuggestedItemSerializer(many=True, required=False)
    recommendation_badge = serializers.CharField(required=False, allow_blank=True)


class ReorderProducerChangedItemSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField(required=False)
    product_name = serializers.CharField(required=False)
    original_producer_id = serializers.IntegerField()
    original_producer_name = serializers.CharField()
    current_producer_id = serializers.IntegerField()
    current_producer_name = serializers.CharField()


class ReorderSelectionSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["keep", "replace", "skip"])
    selected_product_id = serializers.IntegerField(required=False, allow_null=True)
    inventory_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        action = attrs["action"]

        if action == "skip":
            return attrs

        if attrs.get("quantity") in (None, ""):
            raise serializers.ValidationError(
                {"quantity": "Quantity is required for keep and replace actions."}
            )

        if attrs.get("inventory_id") in (None, ""):
            raise serializers.ValidationError(
                {"inventory_id": "Inventory is required for keep and replace actions."}
            )

        if attrs.get("selected_product_id") in (None, ""):
            raise serializers.ValidationError(
                {
                    "selected_product_id": "Selected product is required for keep and replace actions."
                }
            )

        return attrs


class ReorderSelectionRequestSerializer(serializers.Serializer):
    selections = ReorderSelectionSerializer(many=True, required=False)


class ReorderResponseSerializer(serializers.Serializer):
    addable_items = ReorderAddableItemSerializer(many=True, required=False)
    added_items = ReorderAddedItemSerializer(many=True)
    unavailable_items = ReorderUnavailableItemSerializer(many=True)
    quantity_adjusted_items = ReorderQuantityAdjustedItemSerializer(many=True)
    price_changed_items = ReorderPriceChangedItemSerializer(many=True)
    producer_changed_items = ReorderProducerChangedItemSerializer(
        many=True, required=False
    )
    message = serializers.CharField()
