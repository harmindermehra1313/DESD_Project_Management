from django.db import models

class Notification(models.Model):
<<<<<<< HEAD
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

=======
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, db_column="user")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product", null=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order", null=True)
    type = EnumField(choices=['ORDER_UPDATE', 'PRODUCT_ALERT', 'RECALL', 'SYSTEM', 'PROMOTION', 'MESSAGE'])
>>>>>>> origin/rest_api_placeholders
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
<<<<<<< HEAD
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

=======
    id = models.AutoField(primary_key=True)
    producer = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product")
>>>>>>> origin/rest_api_placeholders
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
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/rest_api_placeholders
