from django.db import models

class Notification(models.Model):
    class Type(models.TextChoices):
        ORDER_UPDATE = 'OU', 'Order Update'
        PRODUCT_ALERT = 'PA', 'Product Alert'
        RECALL = 'RC', 'Recall'
        SYSTEM = 'SYS', 'System'
        PROMOTION = 'PRO', 'Promotion'
        MESSAGE = 'MSG', 'Message'

    user = models.ForeignKey(
        "accounts.User", 
        on_delete = models.CASCADE, 
        related_name = "user_notifications"
    )

    product = models.ForeignKey(
        "products.Product", 
        on_delete = models.CASCADE, 
        related_name = "product_notifications", 
        null = True
    )
    
    order = models.ForeignKey(
        "orders.Order", 
        on_delete = models.CASCADE, 
        related_name = "order_notifications", 
        null = True
    )

    type = models.CharField(
        max_length = 15,
        choices = Type.choices,
        default = Type.MESSAGE
    )

    message = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    read_at = models.DateTimeField(
        null=True
    )

    resolved_at = models.DateTimeField(
        null=True
    )


class RecallNotice(models.Model):
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MED', 'Medium'
        HIGH = 'HI', 'High'
    
    producer = models.ForeignKey(
        "accounts.Producer", 
        on_delete = models.CASCADE, 
        related_name ="producer_notice"
    )

    product = models.ForeignKey(
        "products.Product", 
        on_delete = models.CASCADE, 
        related_name = "product_notice"
    )

    recall_reason = models.TextField()

    Severity = models.CharField(
        max_length = 10,
        choices = Severity.choices
    )

    issued_at = models.DateTimeField()

    resolved_at = models.DateTimeField(
        null=True
    )


class RecallNotification(models.Model):
    class Notified_by(models.TextChoices):
        EMAIL = 'EML', 'Email'
        SMS = 'SMS', 'SMS'
        APP = 'APP', 'App'
        PHONE = 'PNE', 'Phone'

    recall = models.ForeignKey(
        RecallNotice, 
        on_delete = models.CASCADE, 
        related_name = "recall_recall"
    )
    customer = models.ForeignKey(
        "accounts.Customer", 
        on_delete = models.CASCADE, 
        related_name = "customer_recall"
    )

    order = models.ForeignKey(
        "orders.Order", 
        on_delete = models.CASCADE, 
        related_name = "order_recall"
    )

    notified_at = models.DateTimeField(
        auto_now_add = True
    )

    Notified_by = models.CharField(
        max_length = 10,
        choices = Notified_by.choices,
        default = Notified_by.EMAIL
    )

    acknowledged = models.BooleanField(
        default = False
    )


class TraceabilityRecord(models.Model):
    order_item = models.ForeignKey(
        "orders.OrderItem", 
        on_delete = models.CASCADE, 
        related_name = "order_tracebility"
    )

    product = models.ForeignKey(
        "products.Product", 
        on_delete = models.CASCADE, 
        related_name ="product_tracebility"
    )

    producer = models.ForeignKey(
        "accounts.Producer", 
        on_delete = models.CASCADE, 
        related_name ="producer_tracebility"
    )

    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete = models.CASCADE, 
        related_name ="customer_tracebility"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True
    )