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
    order_status = serializers.CharField(source="status", read_only=True)
    total = serializers.DecimalField(
        source="total_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    producer_names = serializers.SerializerMethodField()
    delivery_date = serializers.SerializerMethodField()
    collection_date = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "delivery_date",
            "collection_date",
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

    def get_delivery_date(self, obj: Order):
        """
        Return a single top-level delivery date only when every producer
        summary is marked for delivery and all dates match.

        None is returned for collection-only, mixed-fulfilment, or
        conflicting-date orders.
        """
        summaries = list(obj.producer_summaries.all())

        if not summaries:
            return None

        if any(summary.delivery_or_collection != "DEL" for summary in summaries):
            return None

        delivery_dates = [
            summary.delivery_date
            for summary in summaries
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(delivery_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None

    def get_collection_date(self, obj: Order):
        """
        Return a single top-level collection date only when every producer
        summary is marked for collection and all dates match.

        None is returned for delivery-only, mixed-fulfilment, or
        conflicting-date orders.
        """
        summaries = list(obj.producer_summaries.all())

        if not summaries:
            return None

        if any(summary.delivery_or_collection != "COL" for summary in summaries):
            return None

        collection_dates = [
            summary.delivery_date
            for summary in summaries
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(collection_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None


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

    This representation is used in order detail responses where a single
    order may contain multiple producers with different fulfilment details.
    """

    producer_name = serializers.CharField(source="producer.farm_name", read_only=True)

    class Meta:
        model = ProducerOrderSummary
        fields = [
            "id",
            "producer_id",
            "producer_name",
            "status",
            "delivery_or_collection",
            "delivery_date",
            "delivery_time_slot",
            "subtotal",
            "vat_total",
            "commission_total",
            "payout_amount",
            "address_line1",
            "address_line2",
            "city",
            "postcode",
            "special_instructions",
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Serialiser for full order detail responses.

    This serializer exposes:
    - top-level order metadata
    - item-level detail
    - producer-level breakdown
    - derived delivery address
    - masked payment method text
    """

    order_number = serializers.CharField(source="unique_reference", read_only=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)
    producer_breakdown = ProducerOrderSummarySerializer(
        source="producer_summaries",
        many=True,
        read_only=True,
    )
    delivery_address = serializers.SerializerMethodField()
    payment_method_masked = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    delivery_date = serializers.SerializerMethodField()
    collection_date = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "delivery_date",
            "collection_date",
            "status",
            "items",
            "producer_breakdown",
            "delivery_address",
            "payment_method_masked",
            "total_price",
        ]

    def get_delivery_date(self, obj: Order):
        """
        Return a single top-level delivery date only when every producer
        summary is marked for delivery and all dates match.

        None is returned for collection-only, mixed-fulfilment, or
        conflicting-date orders so the client relies on producer_breakdown
        for accurate per-producer information.
        """
        summaries = list(obj.producer_summaries.all())

        if not summaries:
            return None

        if any(summary.delivery_or_collection != "DEL" for summary in summaries):
            return None

        delivery_dates = [
            summary.delivery_date
            for summary in summaries
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(delivery_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None

    def get_collection_date(self, obj: Order):
        """
        Return a single top-level collection date only when every producer
        summary is marked for collection and all dates match.

        None is returned for delivery-only, mixed-fulfilment, or
        conflicting-date orders so the client relies on producer_breakdown
        for accurate per-producer information.
        """
        summaries = list(obj.producer_summaries.all())

        if not summaries:
            return None

        if any(summary.delivery_or_collection != "COL" for summary in summaries):
            return None

        collection_dates = [
            summary.delivery_date
            for summary in summaries
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(collection_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None

    def get_delivery_address(self, obj: Order) -> dict | None:
        """
        Return a single top-level fulfilment address when that address can be
        represented truthfully at order level.

        Rules:
        - delivery-only orders:
            return the customer's order delivery address
        - collection-only orders:
            return the pickup address only if every producer summary points
            to the same collection location
        - mixed fulfilment orders:
            return None because no single address represents the whole order

        Returning None for mixed or inconsistent fulfilment prevents the API
        from exposing a misleading address at top level.
        """
        summaries = list(obj.producer_summaries.all())

        if not summaries:
            return None

        fulfilment_modes = {summary.delivery_or_collection for summary in summaries}

        if fulfilment_modes == {"DEL"}:
            address = getattr(obj, "delivery_address", None)
            if not address:
                return None

            return {
                "line_1": address.line1,
                "line_2": address.line2,
                "city": address.city,
                "postcode": address.postcode,
                "type": "delivery",
            }

        if fulfilment_modes == {"COL"}:
            unique_addresses = {
                (
                    summary.address_line1,
                    summary.address_line2,
                    summary.city,
                    summary.postcode,
                )
                for summary in summaries
            }

            if len(unique_addresses) == 1:
                line_1, line_2, city, postcode = unique_addresses.pop()
                return {
                    "line_1": line_1,
                    "line_2": line_2,
                    "city": city,
                    "postcode": postcode,
                    "type": "collection",
                }

            return None

        return None

    def get_payment_method_masked(self, obj: Order) -> str | None:
        """
        Return a masked payment method string for display purposes.

        Fallback order:
        1. precomputed masked value
        2. generated masked card ending text from last four digits
        3. generic placeholder string
        """
        masked = getattr(obj, "payment_method_masked", None)
        if masked:
            return masked

        last4 = getattr(obj, "payment_last4", None)
        if last4:
            return f"**** **** **** {last4}"

        return "Stored payment method"


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
