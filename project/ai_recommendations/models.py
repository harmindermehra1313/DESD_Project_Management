from django.conf import settings
from django.db import models
from django.utils import timezone


class ProductInteraction(models.Model):
    """
    Stores lightweight customer-product interaction events for the
    Task 1 recommender demonstration.
    This is not intended to be a comprehensive event tracking system, but
    rather a simple model to support the demonstration of the Task 1
    """

    class EventType(models.TextChoices):
        VIEW = "view", "View"
        ADD_TO_CART = "addtocart", "Add to cart"
        TRANSACTION = "transaction", "Transaction"

    class Source(models.TextChoices):
        WEB = "web", "Web"
        SYNTHETIC = "synthetic", "Synthetic demo data"
        ORDER_HISTORY = "order_history", "Order history"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_interactions",
        null=True,
        blank=True,
    )

    session_key = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Supports anonymous browsing before login.",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="recommendation_interactions",
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.VIEW,
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.WEB,
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session_key", "-created_at"]),
            models.Index(fields=["product", "event_type"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.product} - {self.event_type}"

    @classmethod
    def weight_for_event(cls, event_type):
        """
        Return the event-strength weighting used by the recommender.

        This follows the report logic:
        view < add-to-cart < transaction.
        """
        return {
            cls.EventType.VIEW: 1.0,
            cls.EventType.ADD_TO_CART: 3.0,
            cls.EventType.TRANSACTION: 5.0,
        }.get(event_type, 1.0)

    @property
    def weight(self):
        return self.weight_for_event(self.event_type)