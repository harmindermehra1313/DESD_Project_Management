from django.db import models
from django_mysql.models import EnumField #pip install django-mysql


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    vat = models.DecimalField(max_digits=4, decimal_places=2)


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    producer_id = models.ForeignKey(Producer, on_delete=models.CASCADE, db_column="producer_id")
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE, db_column="category_id")
    moderated_by_admin_id = models.ForeignKey(ModerationLog, on_delete=models.CASCADE, db_column="moderated_by_admin_id", null=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = EnumField(choices=['KG', 'G', 'L', 'ML', 'EACH', 'PACK', 'BUNCH', 'BOX'])
    image = models.CharField(max_length=255)
    stock_quantity = models.IntegerField(default = 0)
    low_stock_threshold = models.IntegerField(default = 0)
    harvest_date = models.DateTimeField(auto_now_add=True)
    farm_origin = models.CharField(max_length=150)
    organic_certification_status = EnumField(choices=['CERTIFIED', 'NOT_CERTIFIED'])
    storage_guidance = models.TextField(null=True)
    expiry_date = models.DateTimeField(auto_now_add=True)
    expiry_type = EnumField(choices=['BEST_BEFORE', 'USE_BY'])
    availability_start = models.DateTimeField(auto_now_add=True)
    availability_end = models.DateTimeField(auto_now_add=True)
    availability_status = EnumField(choices=['AVAILABLE', 'OUT_OF_STOCK', 'DISCONTINUED'])
    surplus_status = EnumField(choices=['SURPLUS_ACTIVE', 'SURPLUS_EXPIRED'])
    surplus_discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    surplus_expiry = models.DateTimeField(auto_now_add=True, null=True)
    surplus_note = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    status = EnumField(choices=['HIDDEN', 'FLAGGED', 'REMOVED'])
    moderated_at = models.DateTimeField(auto_now_add=True, null=True)

class WholesalePrice(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    mid_quantity = models.IntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

class SurplusProduct(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(auto_now_add=True)

class ProductUpdateHistory(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    field_changed = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)

class Allergen(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)

class ProductAllergen(models.Model): 
    id = models.AutoFiled(primary_key=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    allergen_id = models.ForeignKey(Allergen, on_delete=models.CASCADE, db_column="allergen_id")
    












    

