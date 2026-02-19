from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django_mysql.models import EnumField #pip install django-mysql

class Review(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column="customer_id")
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE, db_column="order_id")
    moderated_by_admin_id = models.ForeignKey(Admin, on_delete=models.CASCADE, db_column="admin_id", null=True)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255)
    text = models.TextField()
    anonymous = models.BooleanField()
    status = EnumField(choices=['PUBLISHED', 'HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ReviewResponse(models.Model):
    id = models.AutoField(primary_key=True)
    review_id = models.ForeignKey(Review, on_delete=models.CASCADE, db_column="review_id")
    producer_id = models.ForeignKey(Producer, on_delete=models.CASCADE, db_column="producer_id")
    moderated_by_admin_id = models.ForeignKey(AdmintionLog, on_delete=models.CASCADE, db_column="moderated_by_admin_id", null=True)
    response_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = EnumField(choices=['PUBLISHED', 'HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)



