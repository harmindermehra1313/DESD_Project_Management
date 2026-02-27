from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, F, Sum, ExpressionWrapper, DecimalField
from django.utils import timezone
from django.db.models.functions import Coalesce

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

    # For guest carts tied to Django sessions
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
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
            # XOR constraint: exactly one of user or session_key must be set
            models.CheckConstraint(
                name="cart_user_xor_session",
                condition=(
                    (Q(user__isnull=False) & Q(session_key__isnull=True))
                    | (Q(user__isnull=True) & Q(session_key__isnull=False))
                ),
            ),
            # Unique active cart per user
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=CartStatus.ACTIVE),
                name="uniq_active_cart_per_user",
            ),
            # Unique active cart per session
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(status=CartStatus.ACTIVE),
                name="uniq_active_cart_per_session",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "updated_at"], name="cart_status_updated_idx"),
        ]

    def __str__(self) -> str:
        who = f"user={self.user_id}" if self.user_id else f"session={self.session_key}"
        return f"Cart({self.pk}) {who} [{self.status}]"

    @classmethod
    def new_guest_cart(cls, *, session_key: str, expires_at=None):
        return cls.objects.create(
            session_key=session_key,
            status=cls.Status.ACTIVE,
            expires_at=expires_at,
        )

    @property
    def item_count(self) -> int:
        # count of distinct lines (CartItems), per your requirement
        return self.items.count()

    @property
    def total_price(self) -> Decimal:
        expr = ExpressionWrapper(
            Coalesce(F("unit_price"), Decimal("0.00")) * F("quantity"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        total = self.items.aggregate(total=Sum(expr))["total"]
        return total or Decimal("0.00")


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

    # Per your spec: DecimalField quantity
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
    )

    # Per your spec: snapshot price when item is added
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,   # keep nullable for easier migration of existing rows
        blank=True,
    )

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
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"

    def save(self, *args, **kwargs):
        # Snapshot price on first save (or if older rows have null unit_price)
        if self.unit_price is None and self.product_id:
            # Assumes products.Product has a DecimalField named `price`
            self.unit_price = self.product.price
        super().save(*args, **kwargs)