"""
orders/api/serializers/receipts.py

Purpose:
Define API serializers for receipt responses.
"""

from __future__ import annotations

from rest_framework import serializers


class ReceiptAddressSerializer(serializers.Serializer):
    line_1 = serializers.CharField()
    line_2 = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    city = serializers.CharField()
    postcode = serializers.CharField()


class ReceiptItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_name = serializers.CharField()
    producer_name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    final_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_vat = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReceiptProducerBreakdownSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    producer_id = serializers.IntegerField()
    producer_name = serializers.CharField()
    status = serializers.CharField()
    delivery_or_collection = serializers.CharField()
    delivery_date = serializers.DateField(required=False, allow_null=True)
    collection_date = serializers.DateField(required=False, allow_null=True)
    delivery_time_slot = serializers.CharField(required=False, allow_null=True)
    collection_time_slot = serializers.CharField(required=False, allow_null=True)
    delivery_address = ReceiptAddressSerializer(required=False, allow_null=True)
    collection_address = ReceiptAddressSerializer(required=False, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    vat_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ReceiptTotalsSerializer(serializers.Serializer):
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    vat = serializers.DecimalField(max_digits=10, decimal_places=2)
    final_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReceiptResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_number = serializers.CharField()
    order_date = serializers.DateTimeField()
    status = serializers.CharField()
    customer_name = serializers.CharField()
    payment_method_display = serializers.CharField(allow_null=True)
    items = ReceiptItemSerializer(many=True)
    producer_breakdown = ReceiptProducerBreakdownSerializer(many=True)
    totals = ReceiptTotalsSerializer()
