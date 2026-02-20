from django.db import models
from django_mysql.models import EnumField

class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey("accounts.User", on_delete=models.CASCADE, db_column="user_id")
    product_id = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product_id", null=True)
    order_id = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order_id", null=True)
    type = EnumField(choices=['ORDER_UPDATE', 'PRODUCT_ALERT', 'RECALL', 'SYSTEM', 'PROMOTION', 'MESSAGE'])
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)
    resolved_at = models.DateTimeField(null=True)


class RecallNotice(models.Model):
    id = models.AutoField(primary_key=True)
    producer_id = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer_id")
    product_id = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product_id")
    recall_reason = models.TextField()
    severity = EnumField(choices=['LOW', 'MEDIUM', 'HIGH'])
    issued_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True)


class RecallNotification(models.Model):
    id = models.AutoField(primary_key=True)
    recall_id = models.ForeignKey(RecallNotice, on_delete=models.CASCADE, db_column="recall_id")
    customer_id = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer_id")
    order_id = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order_id")
    notified_at = models.DateTimeField(auto_now_add=True)
    notified_by = EnumField(choices=['EMAIL', 'SMS', 'APP', 'PHONE'])
    acknowledged = models.BooleanField(default=False)


class TraceabilityRecord(models.Model):
    id = models.AutoField(primary_key=True)
    order_item_id = models.ForeignKey("orders.OrderItem", on_delete=models.CASCADE, db_column="order_item_id")
    product_id = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product_id")
    producer_id = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer_id")
    customer_id = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer_id")
    timestamp = models.DateTimeField(auto_now_add=True)