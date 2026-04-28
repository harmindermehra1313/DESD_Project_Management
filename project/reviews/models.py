from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q


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
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                condition=~Q(status="RMV"),
                name="unique_active_review_per_customer_per_product",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}

        self._validate_required_links(errors)
        self._validate_order_rules(errors)
        self._validate_order_item_rules(errors)
        self._validate_duplicate_review(errors)
        self._validate_text_fields(errors)

        if errors:
            raise ValidationError(errors)

    def _validate_required_links(self, errors):
        if not self.order_id:
            errors["order"] = "A review must be linked to an order."

        if not self.customer_id:
            errors["customer"] = "A review must be linked to a customer."

        if not self.product_id:
            errors["product"] = "A review must be linked to a product."

    def _get_matching_producer_summary_for_order_item(self):
        if not (self.order_item_id and self.order_id and self.order_item.producer_id):
            return None

        return self.order.producer_summaries.filter(
            producer_id=self.order_item.producer_id
        ).first()

    def _validate_order_rules(self, errors):
        if not (self.order_id and self.customer_id and self.product_id):
            return

        if self.order.user_id != self.customer.user_id:
            errors["customer"] = (
                "You can only review products from your own shipped orders."
            )

        if not self.order.items.filter(product_id=self.product_id).exists():
            errors["product"] = (
                "You can only review products that were included in this order."
            )

    def _validate_order_item_rules(self, errors):
        if not (self.order_item_id and self.order_id and self.product_id and self.customer_id):
            return
    
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
                "You can only review products from your own shipped orders."
            )
    
        summary = self._get_matching_producer_summary_for_order_item()
        if not summary or summary.status != summary.Status.SHIPPED:
            errors["order_item"] = (
                "Reviews can only be submitted for order items that have been shipped."
            )

    def _validate_duplicate_review(self, errors):
        if not (self.customer_id and self.product_id):
            return

        duplicate_exists = (
            Review.objects.filter(
                customer_id=self.customer_id,
                product_id=self.product_id,
            )
            .exclude(status=self.Status.REMOVED)
            .exclude(pk=self.pk)
            .exists()
        )

        if duplicate_exists:
            errors["product"] = "You have already reviewed this product."

    def _validate_text_fields(self, errors):
        if self.title is not None:
            self.title = self.title.strip()

        if self.text is not None:
            self.text = self.text.strip()

        if not self.title:
            errors["title"] = "Review title cannot be blank."

        if not self.text:
            errors["text"] = "Review text cannot be blank."

    @property
    def is_anonymous_display(self):
        return bool(self.anonymous)

    @property
    def public_reviewer_name(self):
        """
        Safe public display name for templates, serializers, and API responses.

        Rules:
        - anonymous=True  -> 'Anonymous'
        - anonymous=False -> best available user/customer display name
        """
        if self.is_anonymous_display:
            return "Anonymous"

        customer = getattr(self, "customer", None)
        user = getattr(customer, "user", None)

        if user is not None:
            full_name = getattr(user, "get_full_name", lambda: "")()
            if full_name and full_name.strip():
                return full_name.strip()

            for attr in ("full_name", "username", "email"):
                value = getattr(user, attr, None)
                if value:
                    return str(value).strip()

        for attr in ("full_name", "name"):
            value = getattr(customer, attr, None)
            if value:
                return str(value).strip()

        return "Verified Customer"

    def public_review_data(self):

        return {
            "id": self.pk,
            "title": self.title,
            "text": self.text,
            "rating": self.rating,
            "anonymous": self.anonymous,
            "reviewer_name": self.public_reviewer_name,
            "status": self.status,
            "created_at": self.created_at,
        }

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
