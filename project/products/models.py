from django.db import models
from django.contrib.postgres.fields import ArrayField
from decimal import Decimal


class Category(models.Model):
    class FoodGroups(models.TextChoices):
        MEAT = "MT", "Meat"
        DAIRY_AND_EGGS = "DAE", "Dairy and Eggs"
        FRUIT = "FR", "Fruit"
        VEGETABLES = "VEG", "Vegetables"
        SEASONAL = "SEA", "Seasonal"

    name = models.CharField(max_length=100)

    food_groups = models.CharField(
        max_length=20, choices=FoodGroups.choices, default=FoodGroups.SEASONAL
    )

    description = models.TextField(blank=True)

    vat = models.DecimalField(max_digits=4, decimal_places=2)


class ProductType(models.Model):
    """
    Narrower grouping for similar products inside a category.

    Example:
    - Category: Fruit
    - ProductType: Apple
    - Product: Braeburn Apples
    """

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="product_types",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_product_type_per_category",
            )
        ]

    def __str__(self):
        return f"{self.category.name} / {self.name}"


class Product(models.Model):

    class Unit(models.TextChoices):
        KILOGRAM = "KG", "Kilogram"
        GRAM = "G", "Gram"
        LITER = "L", "Liter"
        MILLILITER = "ML", "Milliliter"
        EACH = "EA", "Each"
        PACK = "PK", "Pack"
        BUNCH = "BN", "Bunch"
        BOX = "BX", "Box"

    class OrganicStatus(models.TextChoices):
        CERTIFIED = "CERTIFIED", "Certified Organic"
        NOT_CERTIFIED = "NOT_CERTIFIED", "Not Certified"

    class Expiry_type(models.TextChoices):
        BESTBEFORE = "BB", "BEST BEFORE"
        USE_BY = "UB", "USE BY"

    class Availability_status(models.TextChoices):
        AVAILABLE = "AV", "Available"
        OUT_OF_STOCK = "OOS", "Out of Stock"
        DISCONTINUED = "DIS", "Discontinued"

    class Surplus_status(models.TextChoices):
        NONE = "NN", "None"
        SURPLUS_ACTIVE = "SA", "Surplus Active"
        SURPLUS_EXPIRED = "SE", "Surplus Expired"

    class Status(models.TextChoices):
        PUBLISHED = 'PUB', 'Published'
        HIDDEN = 'HID', 'Hidden'
        FLAGGED = 'FLG', 'Flagged'
        REMOVED = 'RMV', 'Removed'
        PENDING = 'PND', 'Pending Approval'


    producer = models.ForeignKey(
        "accounts.Producer", on_delete=models.CASCADE, related_name="producer_products"
    )

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="category_products"
    )
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    moderated_by_admin = models.ForeignKey(
        "accounts.Admin",
        on_delete=models.CASCADE,
        related_name="admin_products",
        null=True,
    )

    name = models.CharField(max_length=150)

    description = models.TextField(blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    unit = models.CharField(max_length=5, choices=Unit.choices, default=Unit.EACH)

    image = models.ImageField(upload_to="products/img/", blank=True, null=True)

    low_stock_threshold = models.IntegerField(default=0)

    farm_origin = models.CharField(max_length=150)

    organic_certification_status = models.CharField(
        max_length=15,
        choices=OrganicStatus.choices,
        default=OrganicStatus.NOT_CERTIFIED,
    )

    storage_guidance = models.TextField(null=True)

    availability_start = models.DateTimeField(auto_now_add=True)

    availability_end = models.DateTimeField(auto_now_add=True)

    availability_status = models.CharField(
        max_length=10,
        choices=Availability_status.choices,
        default=Availability_status.OUT_OF_STOCK,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length = 10,
        choices = Status.choices,
        default = Status.PENDING
    )

    moderated_at = models.DateTimeField(auto_now_add=True, null=True)

    def clean(self):
        super().clean()

        if self.product_type_id and self.category_id:
            if self.product_type.category_id != self.category_id:
                raise ValidationError(
                    {
                        "product_type": (
                            "Selected product type does not belong to the selected category."
                        )
                    }
                )

    # Return the wholesale unit price for a given quantity or None if quantity insufficient
    def get_wholesale_price(self, quantity):
        tier = (
            self.product_wholesale.filter(min_quantity__lte=quantity)
            .order_by("-min_quantity")
            .first()
        )

        if tier:
            return tier.unit_price
        else:
            return None


class Inventory(models.Model):

    class ExpiryType(models.TextChoices):
        BEST_BEFORE = "BB", "Best Before"
        USE_BY = "UB", "Use By"

    class SurplusStatus(models.TextChoices):
        NONE = "NN", "None"
        SURPLUS_ACTIVE = "SA", "Surplus Active"
        SURPLUS_EXPIRED = "SE", "Surplus Expired"

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_batches"
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="added_inventory",
    )

    original_quantity = models.IntegerField()
    remaining_quantity = models.IntegerField()

    harvest_date = models.DateField()
    expiry_date = models.DateField()
    expiry_type = models.CharField(
        max_length=11, choices=ExpiryType.choices, default=ExpiryType.BEST_BEFORE
    )

    surplus_status = models.CharField(
        max_length=15, choices=SurplusStatus.choices, default=SurplusStatus.NONE
    )

    surplus_discount_percentage = models.DecimalField(
        max_digits=4, decimal_places=2, null=True
    )

    surplus_expiry = models.DateTimeField(null=True)
    surplus_note = models.TextField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Return the discounted price if surplus is active else normal price
    def get_discounted_price(self):
        base_price = self.product.price

        if self.surplus_status == Inventory.SurplusStatus.SURPLUS_ACTIVE:
            discount_factor = (
                Decimal("100") - self.surplus_discount_percentage
            ) / Decimal("100")
            return base_price * discount_factor
        else:
            return base_price

    def __str__(self):
        return f"{self.product.name} batch ({self.harvest_date})"


class InventoryUpdateHistory(models.Model):
    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name="history"
    )

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)

    field_changed = models.CharField(max_length=100)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    event_type = models.CharField(
        max_length=20,
        choices=[
            ("field_change", "Field Change"),
            ("reduction_started", "Reduction Started"),
            ("reduction_ended", "Reduction Ended"),
        ],
        default="field_change",
    )

    ended_reason = models.CharField(
        max_length=20,
        choices=[("cancelled", "Cancelled"), ("expired", "Expired")],
        null=True,
    )

    snapshot_discount = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    snapshot_expiry = models.DateTimeField(null=True)
    snapshot_note = models.TextField(null=True)


class WholesalePrice(models.Model):

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_wholesale"
    )

    min_quantity = models.IntegerField(default=0)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


class ProductUpdateHistory(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_history"
    )

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="user_products"
    )

    field_changed = models.CharField(max_length=100)

    old_value = models.TextField()

    new_value = models.TextField()

    changed_at = models.DateTimeField(auto_now_add=True)


class Allergen(models.Model):
    class Allergens(models.TextChoices):
        TREENUTS = "TREENUTS", "Tree Nuts"
        SESAME = "SESAME", "Sesame"
        PEANUTS = "PEANUTS", "Peanuts"
        SOYBEANS = "SOYBEANS", "Soybeans"
        MUSTARD = "MUSTARD", "Mustard"
        FISH = "FISH", "Fish"
        MOLLUSCS = "MOLLUSCS", "Molluscs"
        CRUSTACEANS = "CRUSTACEANS", "Crustaceans"
        CELERY = "CELERY", "Celery"
        GLUTEN = "GLUTEN", "Gluten"
        SULPHUR_DIOXIED = "SULPHUR DIOXIED", "Sulphur Dioxide"
        LUPIN = "LUPIN", "Lupin"
        EGG = "EGG", "Egg"
        MILK = "MILK", "Milk"
        NONE = "NONE", "None"

    name = models.CharField(
        max_length=20, choices=Allergens.choices, default=Allergens.NONE, unique=True
    )

    def __str__(self):
        return self.get_name_display()


class ProductAllergen(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_allergen"
    )
    allergen = models.ForeignKey(
        Allergen, on_delete=models.CASCADE, related_name="allergen_products"
    )

    def __str__(self):
        return f"{self.product.name} - {self.allergen.get_name_display()}"
