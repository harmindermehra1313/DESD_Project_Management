from django.db import models
from accounts.models import User, Producer


# ============================================================
# RECIPE MODEL
# ============================================================
class Recipe(models.Model):

    SEASONAL_TAGS = [
        ("SPRING", "Spring"),
        ("SUMMER", "Summer"),
        ("AUTUMN", "Autumn"),
        ("WINTER", "Winter"),
        ("ALL_YEAR", "All Year"),
    ]

    STATUS_CHOICES = [
        ("PUBLISHED", "Published"),
        ("HIDDEN", "Hidden"),
        ("FLAGGED", "Flagged"),
        ("REMOVED", "Removed"),
    ]

    producer = models.ForeignKey(
        Producer,
        on_delete=models.CASCADE,
        related_name="recipes"
    )

    moderated_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_recipes"
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    ingredients = models.JSONField()      # list of ingredients
    instructions = models.JSONField()     # list of steps

    image = models.CharField(max_length=255)

    seasonal_tag = models.CharField(max_length=20, choices=SEASONAL_TAGS)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PUBLISHED")
    moderated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# ============================================================
# RECIPE ↔ PRODUCT LINK TABLE
# ============================================================
class RecipeProduct(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_products"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_recipes"
    )

    def __str__(self):
        return f"{self.recipe.title} → {self.product.name}"


# ============================================================
# FARM STORY MODEL
# ============================================================
class FarmStory(models.Model):

    STATUS_CHOICES = [
        ("PUBLISHED", "Published"),
        ("HIDDEN", "Hidden"),
        ("FLAGGED", "Flagged"),
        ("REMOVED", "Removed"),
    ]

    producer = models.ForeignKey(
        Producer,
        on_delete=models.CASCADE,
        related_name="farm_stories"
    )

    moderated_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_stories"
    )

    title = models.CharField(max_length=255)
    body = models.TextField()
    image = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PUBLISHED")
    moderated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# ============================================================
# FAVOURITE RECIPE MODEL
# ============================================================
class FavouriteRecipe(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favourite_recipes"
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="favourited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "recipe")  # prevents duplicate favourites

    def __str__(self):
        return f"{self.user.name} ❤️ {self.recipe.title}"