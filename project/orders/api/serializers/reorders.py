"""
orders/api/serializers/orders.py

Purpose:
Define API serializers for order history, order detail, and reorder responses.

This module converts Order-related model instances and reorder service
results into response structures suitable for the API layer.

Responsibilities:
- serialise order history list rows
- serialise detailed order item data
- serialise per-producer order breakdown data
- expose derived fields needed by the frontend
- serialise reorder result payloads returned by the service layer

Design notes:
- serializers should transform and present data, not perform query logic
- selectors are responsible for query optimisation before serializer usage
- service-layer reorder results are validated here before being returned
"""

from __future__ import annotations

from rest_framework import serializers

from orders.models import Order, OrderItem, ProducerOrderSummary


class OrderHistorySerializer(serializers.ModelSerializer):
    """
    Serialiser for paginated order history results.

    Output shape is intentionally compact and list-friendly. Derived fields
    are used where API naming differs from internal model naming.
    """

    order_number = serializers.CharField(source="unique_reference", read_only=True)
    order_status = serializers.CharField(source="get_status_display", read_only=True)
    total = serializers.DecimalField(
        source="total_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    producer_names = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "total",
            "order_status",
            "producer_names",
        ]

    def get_producer_names(self, obj: Order) -> list[str]:
        """
        Return unique producer names associated with the order.

        The order history view typically needs a simple producer summary
        rather than the full producer breakdown.
        """
        names: list[str] = []

        for summary in obj.producer_summaries.all():
            producer_name = getattr(summary.producer, "farm_name", None)
            if producer_name and producer_name not in names:
                names.append(producer_name)

        return names


class OrderItemDetailSerializer(serializers.ModelSerializer):
    """
    Serialiser for individual order items inside the order detail response.

    Snapshot fields are preferred where available so historical order data
    remains stable even if related product or producer records later change.
    """

    product_name = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source="original_unit_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    producer = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "quantity",
            "price",
            "producer",
        ]

    def get_product_name(self, obj: OrderItem) -> str:
        """
        Return the historical product name when available.

        Fallback order:
        1. snapshot name stored on the order item
        2. related product name
        3. placeholder text
        """
        snapshot_name = getattr(obj, "product_name_snapshot", None)
        if snapshot_name:
            return snapshot_name

        if obj.product_id and obj.product:
            return obj.product.name

        return "Unknown product"

    def get_producer(self, obj: OrderItem) -> str:
        """
        Return the historical producer name when available.

        Fallback order:
        1. snapshot name stored on the order item
        2. related producer farm name or string form
        3. placeholder text
        """
        snapshot_name = getattr(obj, "producer_name_snapshot", None)
        if snapshot_name:
            return snapshot_name

        if obj.producer_id and obj.producer:
            producer_name = getattr(obj.producer, "farm_name", None)
            if producer_name:
                return producer_name
            return str(obj.producer)

        return "Unknown producer"


class ProducerOrderSummarySerializer(serializers.ModelSerializer):
    """
    Serialiser for producer-level fulfilment and financial breakdown data.

    A single order may contain multiple producers with different fulfilment
    modes, schedules, and addresses. For that reason, fulfilment-specific
    schedule and address data is exposed at producer-summary level rather
    than being forced into a single top-level order representation.

    The underlying model stores one schedule date, one time-slot pair, and
    one address snapshot for the selected fulfilment path. This serializer
    maps those stored values into delivery-specific or collection-specific
    response fields based on the fulfilment mode so the API output remains
    truthful and easy for the frontend to consume.
    """

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
        """
        Build an address object from the summary snapshot fields.

        The producer summary is treated as the historical source of truth for
        fulfilment address data so past orders remain stable even if related
        producer or customer address records later change.
        """
        if not any(
            [
                obj.address_line1,
                obj.address_line2,
                obj.city,
                obj.postcode,
            ]
        ):
            return None

        return {
            "line_1": obj.address_line1,
            "line_2": obj.address_line2,
            "city": obj.city,
            "postcode": obj.postcode,
        }

    def get_delivery_date(self, obj: ProducerOrderSummary):
        """
        Return the producer delivery date only for delivery fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return obj.delivery_date
        return None

    def get_collection_date(self, obj: ProducerOrderSummary):
        """
        Return the producer collection date only for collection fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return obj.delivery_date
        return None

    def get_delivery_time_slot(self, obj: ProducerOrderSummary):
        """
        Return the producer delivery time slot only for delivery fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return obj.delivery_time_slot
        return None

    def get_collection_time_slot(self, obj: ProducerOrderSummary):
        """
        Return the producer collection time slot only for collection fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return obj.delivery_time_slot
        return None

    def get_delivery_address(self, obj: ProducerOrderSummary) -> dict | None:
        """
        Return the producer delivery address only for delivery fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
            return self._build_address_payload(obj)
        return None

    def get_collection_address(self, obj: ProducerOrderSummary) -> dict | None:
        """
        Return the producer collection address only for collection fulfilment.
        """
        if obj.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
            return self._build_address_payload(obj)
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Serialiser for full order detail responses.

    This serializer exposes:
    - top-level order metadata
    - item-level detail
    - producer-level breakdown
    - derived delivery or collection address when it can be represented
      truthfully at order level
    - masked payment method text

    Fulfilment dates are intentionally not exposed at order level because a
    multi-producer order may contain different schedules per producer.
    """

    order_number = serializers.CharField(source="unique_reference", read_only=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)
    status = serializers.CharField(source="get_status_display", read_only=True)

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

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "status",
            "items",
            "producer_breakdown",
            "payment_method_display",
            "total_price",
        ]

    def get_payment_method_display(self, obj: Order) -> str | None:
        """
        Return a user-friendly payment method label for display.

        Payment records are treated as the source of truth. A successful
        payment is preferred when present; otherwise the most recent payment
        record is used.

        For card payments, a masked card number is returned when last-four
        digits are available. For all other payment methods, the configured
        Django choices display label is returned.
        """
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


class ReorderUnavailableItemSerializer(serializers.Serializer):
    """Serializer for items that could not be added during reorder."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    reason = serializers.CharField()
    producer_id = serializers.IntegerField(required=False)
    producer_name = serializers.CharField(required=False)


class ReorderQuantityAdjustedItemSerializer(serializers.Serializer):
    """Serializer for items added with reduced quantity."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    reason = serializers.CharField()


class ReorderPriceChangedItemSerializer(serializers.Serializer):
    """Serializer for items whose price changed since the original order."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReorderAddedItemSerializer(serializers.Serializer):
    """Serializer for items successfully added to the cart during reorder."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    inventory_id = serializers.IntegerField()


class ReorderResponseSerializer(serializers.Serializer):
    """
    Top-level serializer for the reorder service response payload.

    This serializer validates the shape of the service result before the
    API view returns it to the client.
    """

    added_items = ReorderAddedItemSerializer(many=True)
    unavailable_items = ReorderUnavailableItemSerializer(many=True)
    quantity_adjusted_items = ReorderQuantityAdjustedItemSerializer(many=True)
    price_changed_items = ReorderPriceChangedItemSerializer(many=True)
    message = serializers.CharField()
