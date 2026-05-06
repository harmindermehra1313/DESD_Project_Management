# In python, numbers are saved as binary floating point internally. Prices should not be binary floating points numbers (0.30000000000000004). So, Decimal makes it as base 10 Decimal (0.3)
from decimal import Decimal

from django.conf import settings

# MinValueValidator is a built in Django validator that ensures a numeric fields value is not less than a specified limit value. It supports custom error messages via the message argument. It raises a validation error.
from django.core.validators import MinValueValidator

# models from django.db is used to define tables, columns, relationships, rules/constraints, etc. Django then generates the SQL via migrations. models.Model gives ORM features like .object.create(), .object.filter(), etc.
from django.db import models

# Q: It is used to build complex query conditions (like OR, NOT, or grouped logic). Because normally django filters are ANDed together.
# F: It is a Django ORM expression that is used to refer to a model field directly inside a database query. It can avoid race conditions by making single atomic updates. That makes it safer and faster to use.
# Sum: It is a Django ORM aggregation function. Used often with .aggregate(). Sum adds up values across many rows and return the total.
# ExpressionWrapper: It is a Django ORM tool that builds a calculated expression in a query and explicitly tells Django what type the result should be. It basically tells output type.Best for when doing arithmetic across different field types (Decimal * Integer).
# DecimalField: It is the Django model field type for exact decimal numbers. Its used when precise values are needed like money, prices, tax, etc.
from django.db.models import Q, F, Sum, ExpressionWrapper, DecimalField

# timezone is Django's toolkit for working with timezone-aware datetimes safely and consistently. Pythons datetime.now() returns a naive datetime. So, pythons built in and timezone should not mix to avoid errors like TypeError, wrong expire logic error, etc.
from django.utils import timezone

# Coalesce: It is used to replace NULL with a fallback value inside a database query. For example, if calculated value is NULL, it returns 0. If a field is NULL, it returns a string.
from django.db.models.functions import Coalesce


# models.TextChoices allows to store status like cart status as a safe, limited set of allowed string values while still being human readable in admin/UI. The first part (ACTIVE) is stored value in DB and second part (Active) is display label. Also it helps getting rid of variations like “abandoned”, “ABANDON”, “Abandond” in the DB.
class CartStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    MERGED = "MERGED", "Merged"
    CHECKED_OUT = "CHECKED_OUT", "Checked out"
    ABANDONED = "ABANDONED", "Abandoned"


class Cart(models.Model):
    Status = CartStatus

    """
    # user = models.ForeignKey(...) (Field): 
    Signature: ForeignKey(to, on_delete, **options)
        - Creates many-to-one relationship as many carts can belong to one user.
        - In DB, it creates a column like user_id.
        
    # settings.AUTH_USER_MODEL (First positional argument of parameter - to): 
        - Points to whatever User model is being used (auth.User or accounts.User)
        
    # models.CASCADE (Second positional argument of paramater - on_delete ):
        - CASCADE makes if a linked user is deleted their carts will also get deleted.
    
    # True (Extra keyword argument for parameter - null):
        - This makes user_id can be NULL. So that a cart can exist without a user (like guest user).
    
    # True (Extra keuword argument for parameter - blank):
        - This is for forms/Admin validation and not for database. 
        - Usually paired with null param to make it optional in both DB and forms.
        
    # "carts" (Extra keyword argument for parameter - related_name):
        - Controls the reverse relationship name from the User side (user.cart.all()).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )

    """
    # session_key = models.CharField(...):
    Signature: class CharField(max_length, **options)
        - Its a model field for short and structured text.
        - Creates a string/varchar column in database.
    
    # max_length = 40: 
        - This makes a text column with max length 40.
        - 40 chars is a common safe size.
    
    # db_index = True:
        -  This adds a database index on field (session_key).
        - It makes queries like Model.objects.filter(...) much faster.
        - Without it, DB might scan the whole cart table.
    """
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
    )
    """
    # choices=CartStatus.choices:
        - This restricts the allowed values to the options defined in CartStatus()
    
    # default=CartStatus.Active:
        - If a cart is created without specifying status, Django sets it to "ACTIVE"
    
    """
    status = models.CharField(
        max_length=20,
        choices=CartStatus.choices,
        default=CartStatus.ACTIVE,
        db_index=True,
    )

    """
    # models.DateTimeField(...): 
    Signature: DateTimeField (
        verbose_name=None,
        name=None,
        auto_now=False,
        auto_now_add=False,
        **options
    
    # default=timezone.now:
        - Default is timezone aware datetime.
        - The function is passed (timezone.now) not called (timezone.now()).
            - Calling the function would run once at import time that makes every row get same timestamp.Thats why it is passed instead.
    
    # editable=False:
        - It can not be edited. 
    )
    """
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    
    """
    auto_now=True: Sets the field to current time automatically.
    """
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    """
    to="self:
        - 
    on_delete=models.SET_NULL:
        - If Cart A (source) merged into Cart B (Destination), later Cart B is deleted, then Cart A stays in the database and becomes NULL. For this logic to happen, null=True is required.
    
    related_name="merged_from_carts":
        - It means "Which carts were merged into this cart?"
        - Example:
        Cart1.merged_into_cart_id == 10 # Cart 1 merged into Cart 10
        Cart2.merged_into_cart_id == 10 # Cart 2 merged into Cart 10
        Cart10.merged_from_carts.all() # returns [Cart1, Cart2]
    """
    merged_into_cart = models.ForeignKey(
        to= "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_from_carts",
    )
    """
    Class Meta is an optional inner class inside a model/serializer/form. 
        - It is actually settings for the outer class. 
        - Configurations like db_table, constraints, etc are put here.
    """
    class Meta:
        """
        constraints=[...]:
            - It is the declarative schema constraint specification for a Django Model.
            - Django compiles these into DDL statements (DDL = Data Definition Language like CREATE, ALTER, DROP) via migrations that create database constraints.
            - Violating a constraint raises DB error like IntegrityError.
        """
        constraints = [
            # models.CheckConstraint(...) is a rule the database must verify is true for every row on INSERT/UPDATE. If the rule is false. the DB rejects the write and raises IntegrityError.
            models.CheckConstraint(
                # name="" is an identifier for the constraint.
                name="cart_user_xor_session",
                # condition is the predicate for a partial/conditional constraint. 
                condition=(
                    # Exactly one of user or session_key must be set.
                    # __isnull is a Django field lookup used in queries and constraints.
                    (Q(user__isnull=False) & Q(session_key__isnull=True))
                    | (Q(user__isnull=True) & Q(session_key__isnull=False))
                ),
            ),
            # models.UniqueConstraint(...) defines a database-level uniqueness rule like the DB will reject any INSERT/UPDATE that would create a duplicate for the specified columns (optionally only for rows matching a condition).
            models.UniqueConstraint(
                # unique field which means the user column must be unique within the rows the constraint applies to.
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
        """
        An index is a DB data structure, usually a B-tree, that makes certain queries faster at the cost of extra storage and slightly slower writes.
        """
        indexes = [
            # models.Index(...) defines a database index to speed up queries. This makes filtering faster. This also can do multi column index. 
            models.Index(
                # fields=["fieldA","fieldB"] creates a composite (multi-column) index where the index key is (fieldA. fieldB) in that order. The leftmost-prefix (fieldA) rules.
                fields=["status", "-updated_at"], name="cart_status_updated_idx"
            ),
        ]
    """
    Python calls __str__ when it needs a string of the opbject. Django uses it in the admin, shell, logs and dropdowns for ForeignKeys.
    """
    def __str__(self) -> str:
        who = f"user={self.user_id}" if self.user_id else f"session={self.session_key}"
        return f"Cart({self.pk}) {who} [{self.status}]"

    """
    @classmethod turns a normal method into a class method. It receives the class as the first argument (cls) instead of instrance (self). Class method is used when creating/fetching/converting object. Normal method is used when  using or modifying an existing object.
    """
    @classmethod
    # cls = the class object not instance.
    # * = This makes the parameters after it keyword-only arguments.
    # session_key: str = This is a type hint. session_key should be a string.
    # expires_at=None = Optional argument with default None.
    def new_guest_cart(cls, *, session_key: str, expires_at=None):
        """
        cls = cls is the model class not an object.
        cls.objects = This is the model manager.
        cls.objects.create(...) = It does 3 tasks. 
        1) Construct the instance.
        2) Save it to the db.
        3) Return the saved instance (A real model instance).
        """
        return cls.objects.create(
            session_key=session_key,
            status=cls.Status.ACTIVE,
            expires_at=expires_at,
        )
    """
    @property turns a method into a computed attribute. In normal method, its cart.is_active() basically calling it. But with property its cart.is_active without parentheses. However, a @property CANNOT accept arguments, so if parameter needed, a normal method is the best choice.
    """
    @property
    def item_count(self) -> int:
        # count of distinct lines (CartItems)
        return self.items.count()

    """
    # total_price() returns the total cost of a cart. It is computed as: sum of (unit_price × quantity) for every item in the cart. It is designed to be safe if some prices are missing (NULL) and to always return a Decimal but never None. 
    
    """
    @property
    def total_price(self) -> Decimal:
        expr = ExpressionWrapper(
            Coalesce(F("unit_price"), Decimal("0.00")) * F("quantity"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        total = self.items.aggregate(total=Sum(expr))["total"]
        return total or Decimal("0.00")

    @property
    def total_quantity(self) -> int:
        total = self.items.aggregate(total=Coalesce(Sum("quantity"), Decimal("0")))[
            "total"
        ]
        return int(total)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    # product = models.ForeignKey(
    #     "products.Product",
    #     on_delete=models.CASCADE,
    #     related_name="cart_items",
    # )
    inventory = models.ForeignKey(
        "products.Inventory",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    # DecimalField quantity
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
    )

    # Snapshot price when item is added
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,  # keep nullable for easier migration of existing rows
        blank=True,
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # models.UniqueConstraint(
            #     fields=["cart", "product"],
            #     name="uniq_cart_product",
            # ),
            models.UniqueConstraint(
                fields=["cart", "inventory"],
                name="uniq_cart_item",
            ),
            models.CheckConstraint(
                name="cartitem_quantity_gt_0",
                condition=Q(quantity__gt=0),
            ),
        ]
        # indexes = [
        #     models.Index(fields=["cart", "product"], name="cartitem_cart_product_idx"),
        # ]
        indexes = [
            models.Index(fields=["cart", "inventory"], name="cartitem_cart_inventory_idx"),
        ]
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"

    def save(self, *args, **kwargs):
        # Snapshot price on first save (or if older rows have null unit_price)
        if self.unit_price is None and self.product_id:
            self.unit_price = self.product.price
        super().save(*args, **kwargs)
