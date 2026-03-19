"""
orders/api/serializers/reorders.py

Purpose:
Define API serializers for order history, order detail, and reorder responses.
"""

from __future__ import annotations

from rest_framework import serializers

from orders.models import Order, OrderItem, ProducerOrderSummary


class OrderHistorySerializer(serializers.ModelSerializer):
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
        names: list[str] = []

        for summary in obj.producer_summaries.all():
            producer_name = getattr(summary.producer, "farm_name", None)
            if producer_name and producer_name not in names:
                names.append(producer_name)

        return names


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


class ReorderAddableItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    added_quantity = serializers.IntegerField()
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReorderProducerChangedItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    original_producer_id = serializers.IntegerField()
    original_producer_name = serializers.CharField()
    current_producer_id = serializers.IntegerField()
    current_producer_name = serializers.CharField()


class ReorderResponseSerializer(serializers.Serializer):
    addable_items = ReorderAddableItemSerializer(many=True, required=False)
    added_items = ReorderAddedItemSerializer(many=True)
    unavailable_items = ReorderUnavailableItemSerializer(many=True)
    quantity_adjusted_items = ReorderQuantityAdjustedItemSerializer(many=True)
    price_changed_items = ReorderPriceChangedItemSerializer(many=True)
    producer_changed_items = ReorderProducerChangedItemSerializer(many=True, required=False)
    message = serializers.CharField()