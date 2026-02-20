from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django_mysql.models import EnumField #pip install django-mysql

class Review(models.Model):
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, db_column="product")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, db_column="customer")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_column="order")
    moderated_by_admin = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="admin", null=True)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255)
    text = models.TextField()
    anonymous = models.BooleanField()
    status = EnumField(choices=['PUBLISHED', 'HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ReviewResponse(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, db_column="review")
    producer = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer")
    moderated_by_admin = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="moderated_by_admin", null=True)
    response_text = models.TextField(blank=True)
    status = EnumField(choices=['PUBLISHED', 'HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)