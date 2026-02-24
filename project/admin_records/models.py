from django.db import models

class SecurityLog(models.Model):
    class Event_type(models.TextChoices):
        LOGIN_SUCCESS = 'LS', 'Login Success', 
        LOGIN_FAILURE = 'LF', 'Login Failure', 
        PASSWORD_RESET = 'PR', 'Password Reset', 
        ACCOUNT_LOCKED = 'AL', 'Account Locked', 
        TOKEN_REFRESH = 'TR', 'Token Refresh', 
        SUSPICIOUS_ACTIVITY = 'SA', 'Suspicious Activity', 
        PERMISSION_DENIED = 'PD', 'Permission Denied', 
        LOGOUT = 'LO', 'Logout'

    user = models.ForeignKey(
        "accounts.User", 
        on_delete=models.CASCADE, 
        related_name = "user_security", 
        null=True
    )
    
    event_type = models.CharField(
        max_length = 20,
        choices = Event_type.choices,
        default = Event_type.ACCOUNT_LOCKED
    )

    ip_address = models.CharField(
        max_length=45
    )

    user_agent = models.TextField()

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    metadata = models.JSONField(
        null=True
    )


class AdminPost(models.Model):
    class Category(models.TextChoices):
        ANNOUNCEMENT = 'AN', 'Announcement'
        UPDATE = 'UP', 'Update'
        MAINTENANCE = 'MTN', 'Maintenance'
        POLICY = 'POL', 'Policy'
        PROMOTION = 'PRO', 'Promotion'

    admin = models.ForeignKey("accounts.Admin", 
        on_delete = models.CASCADE, 
        related_name = "admin_post"
    )

    title = models.CharField(
        max_length=255
    )

    body = models.TextField()

    category = models.CharField(
        max_length=20,
        choices=Category.choices
    )
    
    image = models.CharField(
        max_length=255, 
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )


class ModerationLog(models.Model):
    class ContentType(models.TextChoices):
        RECIPE = 'REC', 'Recipe'
        FARM_STORY = 'FS', 'Farm Story'
        PRODUCT = 'PRO', 'Product'
        RECALL_NOTICE = 'RN', 'Recall Notice'
        REVIEW = 'REV', 'Review'
        OTHER = 'OTH', 'Other'

    class Action(models.TextChoices):
        FLAGGED = 'FLG', 'Flagged'
        APPROVED = 'APP', 'Approved'
        REJECTED = 'REJ', 'Rejected'
        REMOVED = 'REM', 'Removed'
        RESTORED = 'RES', 'Restored'

    admin = models.ForeignKey(
        "accounts.Admin", 
        on_delete = models.CASCADE, 
        related_name = "admin_action"
    )

    producer = models.ForeignKey(
        "accounts.Producer", 
        on_delete = models.CASCADE, 
        related_name = "producer_action"
    )

    content_type = models.CharField(
        max_length = 20,
        choices = ContentType.choices)
    
    content = models.IntegerField() #May need to be updated to be polymorphic 

    action = models.CharField(
        max_length=15, 
        choices=Action.choices
    )

    reason = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )


class DistanceRecord(models.Model):
    producer_postcode = models.CharField(
        max_length=20
    )
    
    customer_postcode = models.CharField(
        max_length=20
    )
    
    distance_miles = models.DecimalField(
        max_digits=10, 
        decimal_places=2
    )

    calculated_at = models.DateTimeField(
        auto_now_add=True
    )