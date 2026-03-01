from django.db import models
from django.contrib.postgres.fields import ArrayField
from decimal import Decimal

class Category(models.Model):
    class FoodGroups(models.TextChoices):
        MEAT = 'MT', 'Meat'
        DAIRY_AND_EGGS = 'DAE', 'Dairy and Eggs'
        FRUIT = 'FR', 'Fruit'
        VEGETABLES = 'VEG', 'Vegetables'
        SEASONAL = 'SEA', 'Seasonal'

    name = models.CharField(
        max_length=100
    )

    food_groups = models.CharField(
        max_length = 20,
        choices = FoodGroups.choices,
        default=FoodGroups.SEASONAL

    )

    description = models.TextField(
        blank = True
    )

    vat = models.DecimalField(
        max_digits=4, 
        decimal_places=2
    )


class Product(models.Model):

    class Unit(models.TextChoices):
        KILOGRAM = 'KG', 'Kilogram'
        GRAM     = 'G',  'Gram'
        LITER    = 'L',  'Liter'
        MILLILITER  = 'ML', 'Milliliter'
        EACH     = 'EA', 'Each'
        PACK     = 'PK', 'Pack'
        BUNCH    = 'BN', 'Bunch'
        BOX      = 'BX', 'Box'

    
    class OrganicStatus(models.TextChoices):
        CERTIFIED = 'CERTIFIED', 'Certified Organic'
        NOT_CERTIFIED = 'NOT_CERTIFIED', 'Not Certified'


    class Expiry_type(models.TextChoices):
        BESTBEFORE = 'BB', 'BEST BEFORE'
        USE_BY = 'UB', 'USE BY'


    class Availability_status(models.TextChoices):
        AVAILABLE = 'AV', 'Available'
        OUT_OF_STOCK = 'OOS', 'Out of Stock'
        DISCONTINUED = 'DIS', 'Discontinued'


    class Surplus_status(models.TextChoices):
        NONE = 'NN', 'None'
        SURPLUS_ACTIVE = 'SA', 'Surplus Active'
        SURPLUS_EXPIRED = 'SE', 'Surplus Expired'


    class Status(models.TextChoices):
        PUBLISHED = 'PUB', 'Published'
        HIDDEN = 'HID', 'Hidden'
        FLAGGED = 'FLG', 'Flagged'
        REMOVED = 'RMV', 'Removed'


    producer = models.ForeignKey(
        "accounts.Producer", 
        on_delete = models.CASCADE, 
        related_name = "producer_products"
    )

    category = models.ForeignKey(
        Category, 
        on_delete = models.CASCADE, 
        related_name = "category_products"
    )

    moderated_by_admin = models.ForeignKey(
        "accounts.Admin",
        on_delete = models.CASCADE, 
        related_name = "admin_products", 
        null = True
    )

    name = models.CharField(
        max_length=150
    )

    description = models.TextField(
        blank = True
    )

    price = models.DecimalField(
        max_digits = 10, 
        decimal_places = 2
    )

    unit = models.CharField(
        max_length = 5,
        choices = Unit.choices,
        default = Unit.EACH
    )

    image = models.ImageField(
        upload_to = 'products/'
    )

    stock_quantity = models.IntegerField(
        default = 0
    )

    low_stock_threshold = models.IntegerField(
        default = 0
    )
    
    harvest_date = models.DateTimeField()

    farm_origin = models.CharField(
        max_length = 150
    )

    organic_certification_status = models.CharField(
        max_length = 15,
        choices = OrganicStatus.choices,
        default = OrganicStatus.NOT_CERTIFIED
    )  

    storage_guidance = models.TextField(
        null = True
    )

    expiry_date = models.DateTimeField()

    expiry_type = models.CharField(
        max_length = 11,
        choices = Expiry_type.choices,
        default = Expiry_type.BESTBEFORE
    )

    availability_start = models.DateTimeField(
        auto_now_add = True
    )

    availability_end = models.DateTimeField(
        auto_now_add = True
    )

    availability_status = models.CharField(
        max_length = 10,
        choices = Availability_status.choices,
        default = Availability_status.OUT_OF_STOCK
    )

    surplus_status = models.CharField(
        max_length = 15,
        choices = Surplus_status.choices,
        default = Surplus_status.NONE
    )

    surplus_discount_percentage = models.DecimalField(
        max_digits = 5, 
        decimal_places = 2
    )

    surplus_expiry = models.DateTimeField(
        auto_now_add = True, 
        null = True
    )

    surplus_note = models.TextField(
        null = True
    )

    created_at = models.DateTimeField(
        auto_now_add = True
    )

    updated_at = models.DateTimeField(
        auto_now_add = True
    )

    status = models.CharField(
        max_length = 10,
        choices = Status.choices,
        default = Status.PUBLISHED
    )

    moderated_at = models.DateTimeField(
        auto_now_add = True,
        null = True
    )

    # Return the wholesale unit price for a given quantity or None if quantity insufficient
    def get_wholesale_price(self, quantity):
        tier = (
            self.product_wholesale
            .filter(min_quantity__lte=quantity)
            .order_by('-min_quantity')
            .first()
        )

        if tier:
            return tier.unit_price
        else:
            return None
    
    # Return the discounted price if surplus is active else normal price
    def get_discounted_price(self):
        if self.surplus_status == Product.Surplus_status.SURPLUS_ACTIVE:
            discount_factor = (Decimal('100') - self.surplus_discount_percentage) / Decimal('100')
            return self.price * discount_factor
        else:
            return self.price

class WholesalePrice(models.Model):

    product = models.ForeignKey(
        Product, 
        on_delete = models.CASCADE, 
        related_name = "product_wholesale"
    )
    
    min_quantity = models.IntegerField(
        default = 0
    )

    unit_price = models.DecimalField(
        max_digits = 10,
        decimal_places = 2
    )

class ProductUpdateHistory(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete = models.CASCADE, 
        related_name = "product_history"
    )

    user = models.ForeignKey(
        "accounts.User", 
        on_delete = models.CASCADE, 
        related_name = "user_products"
    )

    field_changed = models.CharField(
        max_length = 100
    )

    old_value = models.TextField()

    new_value = models.TextField()

    changed_at = models.DateTimeField(
        auto_now_add = True
    )

class Allergen(models.Model):
    name = models.CharField(
        max_length = 100
    )

class ProductAllergen(models.Model): 
    product = models.ForeignKey(
        Product, 
        on_delete = models.CASCADE, 
        related_name = "product_allergen"
    )
    allergen = models.ForeignKey(
        Allergen, 
        on_delete = models.CASCADE, 
        related_name = "allergen_products"
    )
    












    

