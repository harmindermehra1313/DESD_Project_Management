from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Review(models.Model):
<<<<<<< HEAD
    class Status(models.TextChoices):
        PUBLISHED = 'PUB', 'Published'
        HIDDEN = 'HID', 'Hidden'
        FLAGGED = 'FLG', 'Flagged'
        REMOVED = 'RMV', 'Removed'

    product = models.ForeignKey(
        "products.Product", 
        on_delete=models.CASCADE, 
        related_name = "product_reviews"
    )

    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.CASCADE, 
        related_name = "customer_reviews"
    )

    order = models.ForeignKey(
        "orders.Order", 
        on_delete=models.CASCADE, 
        related_name = "order_reviews"
    )

    moderated_by_admin = models.ForeignKey(
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

=======
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order")
    moderated_by_admin = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="admin", null=True)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255)
>>>>>>> origin/rest_api_placeholders
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
<<<<<<< HEAD
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




=======
    review = models.ForeignKey(Review, on_delete=models.CASCADE, db_column="review")
    producer = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer")
    moderated_by_admin = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="moderated_by_admin", null=True)
    response_text = models.TextField(blank=True)
    status = EnumField(choices=['PUBLISHED', 'HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
>>>>>>> origin/rest_api_placeholders
