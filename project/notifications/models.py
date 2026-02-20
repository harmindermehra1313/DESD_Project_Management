from django.db import models
from django_mysql.models import EnumField

class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, db_column="user")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product", null=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order", null=True)
    type = EnumField(choices=['ORDER_UPDATE', 'PRODUCT_ALERT', 'RECALL', 'SYSTEM', 'PROMOTION', 'MESSAGE'])
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)
    resolved_at = models.DateTimeField(null=True)


class RecallNotice(models.Model):
    id = models.AutoField(primary_key=True)
    producer = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product")
    recall_reason = models.TextField()
    severity = EnumField(choices=['LOW', 'MEDIUM', 'HIGH'])
    issued_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True)


class RecallNotification(models.Model):
    id = models.AutoField(primary_key=True)
    recall = models.ForeignKey(RecallNotice, on_delete=models.CASCADE, db_column="recall")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order")
    notified_at = models.DateTimeField(auto_now_add=True)
    notified_by = EnumField(choices=['EMAIL', 'SMS', 'APP', 'PHONE'])
    acknowledged = models.BooleanField(default=False)


class TraceabilityRecord(models.Model):
    id = models.AutoField(primary_key=True)
    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.CASCADE, db_column="order_item")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product")
    producer = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer")
    timestamp = models.DateTimeField(auto_now_add=True)