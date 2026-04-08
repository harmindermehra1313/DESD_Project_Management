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
        blank=True,
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
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                name="unique_review_per_customer_per_product",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
    
        if not self.order_id:
            errors["order"] = "A review must be linked to an order."
    
        if not self.customer_id:
            errors["customer"] = "A review must be linked to a customer."
    
        if not self.product_id:
            errors["product"] = "A review must be linked to a product."
    
        if errors:
            raise ValidationError(errors)
    
        # Restrict review submission to delivered orders only
        if self.order.status != self.order.Status.COMPLETED:
            errors["order"] = "Reviews can only be submitted for delivered orders."
    
        # The order must belong to the same customer
        if self.order.user_id != self.customer.user_id:
            errors["customer"] = (
                "You can only review products from your own delivered orders."
            )
    
        # Verified purchase check:
        # the reviewed product must exist in the selected completed order
        if not self.order.items.filter(product_id=self.product_id).exists():
            errors["product"] = (
                "You can only review products that were delivered in this order."
            )
    
        # Exact order_item linkage checks
        if self.order_item_id:
            if self.order_item.order_id != self.order_id:
                errors["order_item"] = (
                    "Selected order item does not belong to the selected order."
                )
    
            if self.order_item.product_id != self.product_id:
                errors["product"] = (
                    "Selected order item does not match the reviewed product."
                )
    
            if self.order_item.order.user_id != self.customer.user_id:
                errors["customer"] = (
                    "You can only review products from your own delivered orders."
                )
    
        # Prevent duplicate reviews per customer per product
        if self.customer_id and self.product_id:
            duplicate_exists = (
                Review.objects.filter(
                    customer_id=self.customer_id,
                    product_id=self.product_id,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicate_exists:
                errors["product"] = "You have already reviewed this product."
    
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)