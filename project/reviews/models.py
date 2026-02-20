from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Review(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = 'PUB', 'Published'
        HIDDEN = 'HID', 'Hidden'
        FLAGGED = 'FLG', 'Flagged'
        REMOVED = 'RMV', 'Removed'

    product_id = models.ForeignKey(
        "products.Product", 
        on_delete=models.CASCADE, 
        related_name = "product_reviews"
    )

    customer_id = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.CASCADE, 
        related_name = "customer_reviews"
    )

    order_id = models.ForeignKey(
        "orders.Order", 
        on_delete=models.CASCADE, 
        related_name = "order_reviews"
    )

    moderated_by_admin_id = models.ForeignKey(
        "accounts.Admin", 
        on_delete=models.CASCADE, 
        related_name = "admin_reviews", 
        null=True
    )

    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    title = models.CharField(
        max_length=255
    )

    text = models.TextField()

    anonymous = models.BooleanField(
        default = True
    )

    status = models.CharField(
        max_length = 10,
        choices = Status.choices,
        default = Status.PUBLISHED
    )

    moderated_at = models.DateTimeField(
        auto_now_add=True, 
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

class ReviewResponse(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = 'PUB', 'Published'
        HIDDEN = 'HID', 'Hidden'
        FLAGGED = 'FLG', 'Flagged'
        REMOVED = 'RMV', 'Removed'

    review = models.ForeignKey(
        Review, 
        on_delete=models.CASCADE, 
        related_name = "review_reviews"
    )

    producer = models.ForeignKey(
        "accounts.Producer", 
        on_delete=models.CASCADE, 
        related_name="producer_reviews"
    )
    # moderated_by_admin_id = models.ForeignKey(
    #   "admin_records.AdmintionLog", 
    #   on_delete=models.CASCADE, 
    #   related_name="moderated_by_admin_id", 
    #   null=True
    #) 

    moderated_by_admin = models.ForeignKey(
        "accounts.Admin", 
        on_delete=models.CASCADE, 
        related_name="moderated_by_admin_reviews", 
        null=True
    )

    response_text = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    status = models.CharField(
        max_length = 10,
        choices = Status.choices,
        default = Status.PUBLISHED
    )

    moderated_at = models.DateTimeField(
        auto_now_add=True, 
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )




