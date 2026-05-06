from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# ============================================================
# CUSTOM USER MANAGER
# ============================================================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", "ADMIN")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


# ============================================================
# USER MODEL
# ============================================================
class User(AbstractBaseUser, PermissionsMixin):

    class Role_choices(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        PRODUCER = "PRODUCER", "Producer"
        COMMUNITY_GROUP = "COMMUNITY_GROUP", "Community Group"
        BUSINESS = "BUSINESS", "Business"
        ADMIN = "ADMIN", "Admin"

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=Role_choices)
    created_at = models.DateTimeField(auto_now_add=True)

    # Django-required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # NEW FIELDS FOR SOFT DELETE
    deactivation_reason = models.TextField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deactivated_users"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return f"{self.name} ({self.role})"

# ============================================================
# ADDRESS MODEL
# ============================================================
class Address(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name = "addresses",
        null=True, #allow guest orders
        blank=True,
        db_index=True
    )

    line1 = models.CharField(
        max_length=255
    )

    line2 = models.CharField(
        max_length=255, 
        blank=True, 
        null=True
    )

    city = models.CharField(
        max_length=100
    )

    postcode = models.CharField(
        max_length=20
    )

    is_default_delivery = models.BooleanField(
        default=False
    )

    is_default_billing = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f"{self.line1}, {self.city}"


# ============================================================
# PRODUCER MODEL
# ============================================================
class Producer(models.Model):
    class Payout_methods(models.TextChoices):
        BANK_TRANSFER = 'BT', 'Bank Transfer'
        PAY_PAL = 'PP', 'Pay Pal'
        CHEQUE = 'CHQ', 'Cheque'
        STRIPE = 'STP', 'Stripe Payouts'

    user = models.OneToOneField(
        User, 
        on_delete = models.CASCADE, 
        related_name = "producer_profile"
    )

    approved_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null = True,
        blank = True,
        related_name = "approved_producers"
    )

    stripe_account_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    farm_name = models.CharField(
        max_length=150
    )

    farm_description = models.TextField()

    organic_certification_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )

    farm_postcode = models.CharField(
        max_length=20
    )

    contact_email = models.EmailField()

    contact_phone = models.CharField(
        max_length=20
    )

    email_low_stock_notifications = models.BooleanField(
        default=False
    )

    is_approved = models.BooleanField(
        default=False
    )
    
    approved_at = models.DateTimeField(
        null=True, 
        blank=True
    )

    payout_method = models.CharField(
        max_length=20, 
        choices=Payout_methods
    )

    bank_account_name = models.CharField(
        max_length=150, 
        null=True, 
        blank=True
    )

    bank_account_number = models.CharField(
        max_length=50, 
        null=True, 
        blank=True
    )

    bank_sort_code = models.CharField(
        max_length=20, 
        null=True, 
        blank=True
    )

    paypal_email = models.EmailField(
        null=True, 
        blank=True
    )

    payout_notes = models.TextField(
        null=True, 
        blank=True
    )
    cheque_payee_name = models.CharField(max_length=150, null=True, blank=True)
    cheque_postal_address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.farm_name


# ============================================================
# ADMIN MODEL
# ============================================================
class Admin(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name = "admin_profile"
    )

    permissions_json = models.JSONField()

    def __str__(self):
        return f"Admin: {self.user.name}"


# ============================================================
# CUSTOMER MODEL
# ============================================================
class Customer(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete = models.CASCADE, 
        related_name = "customer_profile"
    )

    organisation_type = models.CharField(
        max_length = 150, 
        null = True, 
        blank = True
    )

    registration_number = models.CharField(
        max_length = 100, 
        null = True, 
        blank = True
    )

    contact_person_name = models.CharField(
        max_length = 150, 
        null = True,
        blank = True
    )

    billing_preferences = models.JSONField(
        null = True, 
        blank = True
    )

    def __str__(self):
        return f"Customer: {self.user.name}"