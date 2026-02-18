from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal



class Order(models.Model):
    class DeliveryOrCollection(models.TextChoices):
        DELIVERY = "DELIVERY", "Delivery"
        COLLECTION = "COLLECTION", "Collection"
        
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for delivery"
        READY_FOR_COLLECTION = "READY_FOR_COLLECTION", "Ready for collection"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete= models.CASCADE,
        related_name="orders",
    )
    
    
    delivery_address = models.ForeignKey(
        "accounts.Address",
        on_delete= models.SET_NULL,
        null= True,
        blank= True,
        related_name = 'orders',
    )

    recurring_order = models.ForeignKey(
        "orders.RecurringOrder",
        on_delete= models.SET_NULL,
        null = True,
        blank= True,
        related_name='generated_orders',
    )
    
    order_date = models.DateTimeField(
        default= timezone.now
    )
    
    delivery_or_collection = models.CharField(
        max_length= 20,
        choices=DeliveryOrCollection.choices,
    )
    
    delivery_date = models.DateTimeField()
    
    total_price = models.DecimalField(
        max_digits= 10,
        decimal_places=2,
        default= Decimal("0.00")
    )
    
    total_discount = models.DecimalField(
        max_digits= 10,
        decimal_places=2,
        default= Decimal("0.00")
    )
    
    final_total_price = models.DecimalField(
        max_digits= 10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    total_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    food_miles_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    status = models.CharField(
        max_length= 30,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    def __str__(self):
        return f"Order #{self.pk} ({self.status})"
    


class OrderItem(models.Model):
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='items',
    )
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='order_items',
    )
    
    producer = models.ForeignKey(
        'accounts.Producer',
        on_delete=models.CASCADE,
        related_name='produced_order_items',
    )
    
    quantity = models.PositiveIntegerField()
    
    original_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    
    commision_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    discount_reason = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )
    
    final_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    food_miles = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )
    
    preparation_deadline = models.DateTimeField()
    
    def __str__(self):
        return f"Item #{self.pk} for order #{self.order.pk}"
    
    

class ProducerOrderSummary(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PREPARING = "PREPARING", "Preparing"
        PACKAGED = "PACKAGED", "Packaged"
        SHIPPED = "SHIPPED", "Shipped"
        CANCELLED = "CANCELLED", "Cancelled"
        
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="producer_summaries",
    )
    
    producer = models.ForeignKey(
        'accounts.Producer',
        on_delete=models.CASCADE,
        related_name="order_summaries",
    )
    
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00")
        )
    
    commission_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00")
        
        )
    payout_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00")
        )

    delivery_date = models.DateTimeField()

    special_instructions = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"ProducerSummary #{self.pk} (Order #{self.order.pk})"
    
    
    
class ProducerOrderStatusHistory(models.Model):
    
    old_status = models.CharField(
        max_length=20, 
        choices=ProducerOrderSummary.Status.choices
        )
    
    new_status = models.CharField(
        max_length=20, 
        choices=ProducerOrderSummary.Status.choices
        )

    producer_order_summary = models.ForeignKey(
        "orders.ProducerOrderSummary",
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="producer_status_updates",
    )

    note = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"History #{self.pk}: {self.old_status} ---> {self.new_status}"    
    

class RecurringOrder(models.Model):
    class RecurrencePattern(models.TextChoices):
        WEEKLY = "WEEKLY", "Weekly"
        FORTNIGHTLY = "FORTNIGHTLY", "Fortnightly"

    class Day(models.TextChoices):
        MON = "MON", "Mon"
        TUE = "TUE", "Tue"
        WED = "WED", "Wed"
        THU = "THU", "Thu"
        FRI = "FRI", "Fri"
        SAT = "SAT", "Sat"
        SUN = "SUN", "Sun"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_orders",
    )

    delivery_address = models.ForeignKey(
        "accounts.Address",          
        on_delete=models.CASCADE,
        related_name="recurring_orders",
    )

    recurrence_pattern = models.CharField(
        max_length=15, 
        choices=RecurrencePattern.choices
        )

    recurrence_day = models.CharField(
        max_length=3,
        choices=Day.choices,
        null=True,
        blank=True,
    )

    delivery_day = models.CharField(
        max_length=3, choices=Day.choices
        )

    special_instructions = models.TextField(
        null=True, 
        blank=True
        )

    status = models.CharField(
        max_length=10, 
        choices=Status.choices, 
        default=Status.ACTIVE
        )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RecurringOrder #{self.pk} ({self.status})"
    
    
class RecurringOrderItem(models.Model):
    recurring_order = models.ForeignKey(
        "orders.RecurringOrder",
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="recurring_order_items",
    )

    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"RecurringItem #{self.pk} (Recurring #{self.recurring_order.pk})"