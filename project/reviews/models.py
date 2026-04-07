from django.apps import apps
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator


class Review(models.Model):

    class Status(models.TextChoices):
        PUBLISHED = "PUB", "Published"
        HIDDEN = "HID", "Hidden"
        FLAGGED = "FLG", "Flagged"
        REMOVED = "RMV", "Removed"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_reviews",
    )

    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.CASCADE,
        related_name="customer_reviews",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="order_reviews",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )

    moderated_by_admin = models.ForeignKey(
        "accounts.Admin",
        on_delete=models.CASCADE,
        related_name="admin_reviews",
        null=True,
    )

    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    title = models.CharField(max_length=255)
    text = models.TextField()
    anonymous = models.BooleanField(default=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PUBLISHED,
    )

    moderated_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        errors = {}

        OrderItem = apps.get_model("orders", "OrderItem")

        # Required relation presence checks
        if not self.order_id:
            errors["order"] = "A review must be linked to an order."
        if not self.customer_id:
            errors["customer"] = "A review must be linked to a customer."
        if not self.product_id:
            errors["product"] = "A review must be linked to a product."

        if errors:
            raise ValidationError(errors)

        # Order must be completed
        if self.order.status != self.order.Status.COMPLETED:
            errors["order"] = "Reviews can only be linked to fulfilled orders."

        # Order must belong to the same customer
        if self.order.customer_id != self.customer_id:
            errors["customer"] = (
                "You can only review products from your own completed orders."
            )

        # Verified purchase check:
        # the reviewed product must exist in the selected order
        purchased_item_qs = OrderItem.objects.filter(
            order_id=self.order_id,
            product_id=self.product_id,
        )

        if not purchased_item_qs.exists():
            errors["product"] = (
                "You can only review products you purchased in this completed order."
            )

        # Optional exact order-item consistency checks
        if self.order_item_id:
            if self.order_item.order_id != self.order_id:
                errors["order_item"] = (
                    "Selected order item does not belong to the selected order."
                )

            if self.order_item.product_id != self.product_id:
                errors["product"] = (
                    "Selected order item does not match the reviewed product."
                )

            if self.order_item.order.customer_id != self.customer_id:
                errors["customer"] = (
                    "You can only review products from your own completed orders."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)