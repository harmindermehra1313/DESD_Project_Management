from __future__ import annotations

from rest_framework import serializers

from orders.models import Order, OrderItem, ProducerOrderSummary


class OrderHistorySerializer(serializers.ModelSerializer):
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

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "delivery_date",
            "total",
            "order_status",
            "producer_names",
        ]

    def get_producer_names(self, obj: Order) -> list[str]:
        names: list[str] = []

        for summary in obj.producer_summaries.all():
            producer_name = getattr(summary.producer, "farm_name", None)
            if producer_name and producer_name not in names:
                names.append(producer_name)

        return names

    def get_delivery_date(self, obj: Order):
        """
        Return a single delivery date only when all producer summaries
        share the same delivery date.

        For multi-vendor orders with different producer delivery dates,
        return None and let the client inspect producer_breakdown in
        the detail endpoint.
        """
        delivery_dates = [
            summary.delivery_date
            for summary in obj.producer_summaries.all()
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(delivery_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None


class OrderItemDetailSerializer(serializers.ModelSerializer):
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


class ProducerOrderSummarySerializer(serializers.ModelSerializer):
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
    order_number = serializers.CharField(source="unique_reference", read_only=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)
    producer_breakdown = ProducerOrderSummarySerializer(
        source="producer_summaries",
        many=True,
        read_only=True,
    )
    delivery_address = serializers.SerializerMethodField()
    payment_method_masked = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    delivery_date = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "order_date",
            "delivery_date",
            "status",
            "items",
            "producer_breakdown",
            "delivery_address",
            "payment_method_masked",
            "total_price",
        ]

    def get_delivery_date(self, obj: Order):
        """
        Return a single top-level delivery date only if every producer
        summary uses the same date. Otherwise return None and rely on
        producer_breakdown for the per-producer truth.
        """
        delivery_dates = [
            summary.delivery_date
            for summary in obj.producer_summaries.all()
            if summary.delivery_date is not None
        ]

        unique_dates = sorted(set(delivery_dates))

        if len(unique_dates) == 1:
            return unique_dates[0]

        return None

    def get_delivery_address(self, obj: Order) -> dict | None:
        address = getattr(obj, "delivery_address", None)
        if not address:
            return None

        return {
            "line_1": getattr(address, "line_1", ""),
            "line_2": getattr(address, "line_2", ""),
            "city": getattr(address, "city", ""),
            "postcode": getattr(address, "postcode", ""),
            "country": getattr(address, "country", ""),
        }

    def get_payment_method_masked(self, obj: Order) -> str | None:
        masked = getattr(obj, "payment_method_masked", None)
        if masked:
            return masked

        last4 = getattr(obj, "payment_last4", None)
        if last4:
            return f"**** **** **** {last4}"

        return "Stored payment method"


class ReorderUnavailableItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    reason = serializers.CharField()
    producer_id = serializers.IntegerField(required=False)
    producer_name = serializers.CharField(required=False)


class ReorderQuantityAdjustedItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    reason = serializers.CharField()


class ReorderPriceChangedItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReorderAddedItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    inventory_id = serializers.IntegerField()


class ReorderResponseSerializer(serializers.Serializer):
    added_items = ReorderAddedItemSerializer(many=True)
    unavailable_items = ReorderUnavailableItemSerializer(many=True)
    quantity_adjusted_items = ReorderQuantityAdjustedItemSerializer(many=True)
    price_changed_items = ReorderPriceChangedItemSerializer(many=True)
    message = serializers.CharField()