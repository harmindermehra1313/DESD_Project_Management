from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
# from django_extensions.db.fields import ShortUUIDField
from shortuuidfield import ShortUUIDField

class Order(models.Model):
    class DeliveryOrCollection(models.TextChoices):
        DELIVERY = "DEL", "Delivery"
        COLLECTION = "COL", "Collection"
        
    class Status(models.TextChoices):
        PENDING = "PEN", "Pending"
        IN_PROGRESS = "IP", "In progress"
        OUT_FOR_DELIVERY = "OFD", "Out for delivery"
        READY_FOR_COLLECTION = "RFC", "Ready for collection"
        COMPLETED = "CMP", "Completed"
        CANCELLED = "CAN", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "orders_for_users",
        null=True,
        blank=True
    )
    
    delivery_address = models.ForeignKey(
        "accounts.Address",
        on_delete = models.CASCADE,
        related_name = 'address_orders',
    )

    recurring_order = models.ForeignKey(
        "orders.RecurringOrder",
        on_delete = models.SET_NULL,
        null = True,
        blank= True,
        related_name = 'generated_orders',
    )

    billing_address = models.ForeignKey(
        "accounts.Address",
        on_delete=models.CASCADE,
        related_name="billing_orders",
        null=True,
        blank=True,
    )

    unique_reference = ShortUUIDField(
        max_length = 10,
        editable = False,
        unique = True,
    )

    order_date = models.DateTimeField(
        default = timezone.now
    )
    
    total_price = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    total_discount = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )

    total_vat = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    final_total_price = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    total_commission = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    food_miles_total = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    status = models.CharField(
        max_length = 30,
        choices = Status.choices,
        default = Status.PENDING
    )

    # Handle guests
    guest_name = models.CharField(max_length=150, null=True, blank=True)
    guest_email = models.EmailField(null=True, blank=True)
    guest_phone = models.CharField(max_length=20, null=True, blank=True)
    is_guest = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Order #{self.pk} ({self.status})"
    


class OrderItem(models.Model):
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete = models.CASCADE,
        related_name = 'items',
    )
    
    product = models.ForeignKey(
        'products.Product',
        on_delete = models.CASCADE,
        related_name = 'order_items',
    )

    inventory = models.ForeignKey(
        'products.Inventory',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    
    producer = models.ForeignKey(
        'accounts.Producer',
        on_delete = models.CASCADE,
        related_name = 'produced_order_items',
    )
    
    quantity = models.PositiveIntegerField()
    
    original_unit_price = models.DecimalField(
        max_digits = 10,
        decimal_places = 2
    )
    
    commission_amount = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    discount_amount = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    discount_reason = models.CharField(
        max_length = 255,
        blank = True,
        default = ""
    )

    vat_amount = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )

    vat_rate = models.DecimalField(
        max_digits = 4,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    final_unit_price = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    food_miles = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )
    
    preparation_deadline = models.DateTimeField()
    
    def __str__(self):
        return f"Item #{self.pk} for order #{self.order.pk}"
    
    

class ProducerOrderSummary(models.Model):
    class Status(models.TextChoices):
        PENDING = "PEN", "Pending"
        PREPARING = "PRE", "Preparing"
        PACKAGED = "PAC", "Packaged"
        SHIPPED = "SHP", "Shipped"
        CANCELLED = "CAN", "Cancelled"
        COMPLETED = "COM", "Completed"
        
    order = models.ForeignKey(
        "orders.Order",
        on_delete = models.CASCADE,
        related_name = "producer_summaries",
    )
    
    producer = models.ForeignKey(
        'accounts.Producer',
        on_delete = models.CASCADE,
        related_name = "order_summaries",
    )
    
    subtotal = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
        )
    
    commission_total = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
        
        )
    
    vat_total = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        default = Decimal("0.00")
    )

    payout_amount = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
        )

    delivery_date = models.DateField()

    delivery_or_collection = models.CharField(
        max_length=20,
        choices=Order.DeliveryOrCollection.choices,
    )

    delivery_time_slot = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)

    special_instructions = models.TextField(
        null=True, 
        blank=True
    )

    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )

    def __str__(self):
        return f"ProducerSummary #{self.pk} (Order #{self.order.pk})"
    
    
    
class ProducerOrderStatusHistory(models.Model):
    
    old_status = models.CharField(
        max_length = 20, 
        choices = ProducerOrderSummary.Status.choices
    )
    
    new_status = models.CharField(
        max_length = 20, 
        choices = ProducerOrderSummary.Status.choices
    )

    producer_order_summary = models.ForeignKey(
        "orders.ProducerOrderSummary",
        on_delete = models.CASCADE,
        related_name = "status_history",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "producer_status_updates",
    )

    note = models.TextField(
        null = True, 
        blank = True
    )

    changed_at = models.DateTimeField(
        default = timezone.now
    )

    def __str__(self):
        return f"History #{self.pk}: {self.old_status} ---> {self.new_status}"    
    

class RecurringOrder(models.Model):
    class RecurrencePattern(models.TextChoices):
        WEEKLY = "WK", "Weekly"
        FORTNIGHTLY = "FN", "Fortnightly"

    class Day(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"
        SAT = "SAT", "Saturday"
        SUN = "SUN", "Sunday"

    class Status(models.TextChoices):
        ACTIVE = "ACT", "Active"
        PAUSED = "PS", "Paused"
        CANCELLED = "CAN", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "user_orders",
    )

    delivery_address = models.ForeignKey(
        "accounts.Address",          
        on_delete = models.CASCADE,
        related_name = "delivery_orders",
    )

    recurrence_pattern = models.CharField(
        max_length = 15, 
        choices = RecurrencePattern.choices
    )

    recurrence_day = models.CharField(
        max_length = 3,
        choices = Day.choices,
        null = True,
        blank = True,
    )

    delivery_day = models.CharField(
        max_length = 3, 
        choices = Day.choices
    )

    special_instructions = models.TextField(
        null = True, 
        blank = True
    )

    status = models.CharField(
        max_length = 10, 
        choices = Status.choices, 
        default = Status.ACTIVE
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    updated_at = models.DateTimeField(
        auto_now = True
    )

    def __str__(self):
        return f"RecurringOrder #{self.pk} ({self.status})"
    
    
class RecurringOrderItem(models.Model):
    recurring_order = models.ForeignKey(
        "orders.RecurringOrder",
        on_delete = models.CASCADE,
        related_name = "items"
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete = models.CASCADE,
        related_name = "recurring_order_items"
    )

    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"RecurringItem #{self.pk} (Recurring #{self.recurring_order.pk})"