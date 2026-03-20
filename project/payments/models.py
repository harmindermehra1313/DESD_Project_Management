from django.conf import settings
from django.db import models
from decimal import Decimal


class Payment(models.Model):
    class Method(models.TextChoices):
        CARD = "CRD", "Card"
        CASH = "CSH", "Cash"
        ACCOUNT_WALLET = "AW", "Account wallet"
        VOUCHER = "VOU", "Voucher"

    class Status(models.TextChoices):
        PENDING = "PEN", "Pending"
        SUCCESS = "SUC", "Success"
        FAILED = "FAI", "Failed"
        REFUNDED = "REF", "Refunded"

    order = models.OneToOneField(
        "orders.Order",
        on_delete = models.CASCADE,
        related_name = "payment",
    )

    stripe_payment_intent = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2
    )

    payment_method = models.CharField(
        max_length = 20, 
        choices = Method.choices
    )

    payment_status = models.CharField(
        max_length = 10, 
        choices = Status.choices, 
        default = Status.PENDING
    )

    transaction_reference = models.CharField(
        max_length = 255, 
        null = True, 
        blank = True
    )

    sandbox_mode = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Payment #{self.pk} for Order #{self.order.pk} ({self.payment_status})"


class ProducerSettlement(models.Model):
    class PayoutStatus(models.TextChoices):
        PENDING = "PEN", "Pending"
        PROCESSING = "PRO", "Processing"
        PAID = "PAI", "Paid"
        FAILED = "FAI", "Failed"

    producer = models.ForeignKey(
        "accounts.Producer",  
        on_delete = models.PROTECT,
        related_name = "settlements"
    )

    settlement_week = models.DateField()

    total_sales = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
    )

    total_commission = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
    )

    payment_reference = models.CharField(
        max_length = 255
    )

    payout_amount = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
    )

    payout_status = models.CharField(
        max_length = 12, 
        choices = PayoutStatus.choices, 
        default = PayoutStatus.PENDING
    )

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ["producer", "settlement_week"],
                name = "uniq_settlement_per_producer_per_week",
            )
        ]

    def __str__(self):
        return f"Settlement #{self.pk} ({self.settlement_week}) for Producer #{self.producer.pk}"


class SettlementLineItem(models.Model):
    settlement = models.ForeignKey(
        "payments.ProducerSettlement",
        on_delete = models.CASCADE,
        related_name = "line_items"
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete = models.PROTECT,
        related_name = "settlement_line_items",
    )

    amount = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2
    )

    commission = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2, 
        default = Decimal("0.00")
    )

    net_amount = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2
    )

    def __str__(self):
        return f"SettlementLineItem #{self.pk} (Settlement #{self.settlement.pk})"