from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
import uuid


class CartStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    MERGED = "MERGED", "Merged"
    CHECKED_OUT = "CHECKED_OUT", "Checked out"
    ABANDONED = "ABANDONED", "Abandoned"

class Cart(models.Model):
    Status = CartStatus
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )

    guest_token = models.UUIDField(
        null=True,
        blank=True,
        unique=True,  
        default=None,
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=CartStatus.choices,
        default=CartStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    merged_into_cart = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_from_carts",
    )

    class Meta:
        constraints = [
            # XOR constraint: exactly one of user or guest_token must be set
            models.CheckConstraint(
                name="cart_user_xor_guest",
                condition=(
                    (Q(user__isnull=False) & Q(guest_token__isnull=True))
                    | (Q(user__isnull=True) & Q(guest_token__isnull=False))
                ),
            ),
            # Unique active cart per user (Postgres partial unique index)
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=CartStatus.ACTIVE),
                name="uniq_active_cart_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "updated_at"], name="cart_status_updated_idx"),
        ]

    def __str__(self) -> str:
        who = f"user={self.user_id}" if self.user_id else f"guest={self.guest_token}"
        return f"Cart({self.pk}) {who} [{self.status}]"

    @classmethod
    def new_guest_cart(cls, *, expires_at=None):
        return cls.objects.create(
            guest_token=uuid.uuid4(),
            status=cls.Status.ACTIVE,
            expires_at=expires_at,
        )


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="uniq_cart_product",
            ),
            models.CheckConstraint(
                name="cartitem_quantity_gt_0",
                condition=Q(quantity__gt=0),
            ),
        ]
        indexes = [
            models.Index(fields=["cart", "product"], name="cartitem_cart_product_idx"),
        ]

    def __str__(self) -> str:
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"