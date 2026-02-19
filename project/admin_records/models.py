from django.db import models
from django_mysql.models import EnumField

class SecurityLog(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey("accounts.User", on_delete=models.CASCADE, db_column="user_id", null=True)
    event_type = EnumField(choices=['LOGIN_SUCCESS', 'LOGIN_FAILURE', 'PASSWORD_RESET', 'ACCOUNT_LOCKED', 'TOKEN_REFRESH', 'SUSPICIOUS_ACTIVITY', 'PERMISSION_DENIED', 'LOGOUT'])
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True)


class AdminPost(models.Model):
    id = models.AutoField(primary_key=True)
    admin_id = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="admin_id")
    title = models.CharField(max_length=255)
    body = models.TextField()
    category = EnumField(choices=['ANNOUNCEMENT', 'UPDATE', 'MAINTENANCE', 'POLICY', 'PROMOTION'])
    image = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ModerationLog(models.Model):
    id = models.AutoField(primary_key=True)
    admin_id = models.ForeignKey("accounts.Admin", on_delete=models.CASCADE, db_column="admin_id")
    producer_id = models.ForeignKey("accounts.Producer", on_delete=models.CASCADE, db_column="producer_id")
    content_type = EnumField(choices=['RECIPE', 'FARM_STORY', 'PRODUCT', 'RECALL_NOTICE', 'REVIEW', 'OTHER'])
    content_id = models.IntegerField() #May need to be updated to be polymorphic 
    action = EnumField(choices=['FLAGGED', 'APPROVED', 'REJECTED', 'REMOVED', 'RESTORED'])
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class DistanceRecord(models.Model):
    id = models.AutoField(primary_key=True)
    producer_postcode = models.CharField(max_length=20)
    customer_postcode = models.CharField(max_length=20)
    distance_miles = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now_add=True)