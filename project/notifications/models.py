from django.db import models

class Notification(models.Model):
    class Type(models.TextChoices):
        ORDER_PLACED = "OP", "Order Placed"
        ORDER_UPDATE = "OU", "Order Update"
        ORDER_CANCELLED = "OC", "Order Cancelled"
        REFUND = "RF", "Refund"
        PRODUCT_ALERT = "PA", "Product Alert"
        RECALL = "RC", "Recall"
        SYSTEM = "SYS", "System"
        PROMOTION = "PRO", "Promotion"
        MESSAGE = "MSG", "Message"
        REVIEW_FLAGGED = "review_flagged", "Review flagged"
        ADMIN_ALERT = "admin_alert", "Admin alert"
        SYSTEM_ALERT = "system_alert", "System alert"
        REVIEW_UPDATE = "review_update", "Review update"

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

    severity = models.CharField(
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

    notified_by = models.CharField(
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

    inventory = models.ForeignKey(
        "products.Inventory",
        on_delete=models.PROTECT,
        related_name="traceability_records",
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
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="traceability_records",
    )

    guest_name = models.CharField(max_length=150, null=True, blank=True)
    guest_email = models.EmailField(null=True, blank=True)
    guest_phone = models.CharField(max_length=20, null=True, blank=True)

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Traceability for OrderItem {self.order_item_id}"