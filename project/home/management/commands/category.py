from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps
from decimal import Decimal

UserModel = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with users, producer, categories, allergens, and products."

    @transaction.atomic
    def handle(self, *args, **options):
        # Load models dynamically
        self.User = apps.get_model("accounts", "User")
        self.Producer = apps.get_model("accounts", "Producer")
        self.Admin = apps.get_model("accounts", "Admin")
        self.Customer = apps.get_model("accounts", "Customer")
        self.Address = apps.get_model("accounts", "Address")

        self.Category = apps.get_model("products", "Category")
        self.Allergen = apps.get_model("products", "Allergen")
        self.Product = apps.get_model("products", "Product")
        self.ProductAllergen = apps.get_model("products", "ProductAllergen")

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding database..."))

        self.create_users()
        self.create_addresses()
        self.create_producers()
        self.create_categories()
        self.create_allergens()
        self.create_products()
        self.create_certified_organic_products()

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # ------------------------------------------------------------
    # USERS
    # ------------------------------------------------------------
    def create_users(self):
        self.admin_user, _ = UserModel.objects.get_or_create(
            email="admin12@gmail.com",
            defaults={
                "name": "John Admin",
                "password": "adminpass1",
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
            }
        )

        self.customer_user, _ = UserModel.objects.get_or_create(
            email="mark412@hotmail.com",
            defaults={
                "name": "Mark Greene",
                "password": "customerpass",
                "role": "CUSTOMER",
            }
        )

        self.admin, _ = self.Admin.objects.get_or_create(
            user=self.admin_user,
            defaults={
                "permissions_json": {
                    "can_moderate": True,
                    "can_manage_producers": True,
                    "can_manage_posts": True,
                    "can_view_security_logs": True,
                }
            }
        )

        self.customer, _ = self.Customer.objects.get_or_create(
            user=self.customer_user
        )

        self.stdout.write(self.style.SUCCESS("Users created or reused."))

    # ------------------------------------------------------------
    # ADDRESS
    # ------------------------------------------------------------
    def create_addresses(self):
        self.customer_address, _ = self.Address.objects.get_or_create(
            user=self.customer_user,
            defaults={
                "line1": "13 Balloon Street",
                "city": "Bristol",
                "postcode": "BS1 3KB",
            }
        )
        self.stdout.write(self.style.SUCCESS("Address created or reused."))

    # ------------------------------------------------------------
    # PRODUCER
    # ------------------------------------------------------------
    def create_producers(self):
        self.producer, _ = self.Producer.objects.get_or_create(
            user=self.admin_user,
            defaults={
                "farm_name": "Blue Cow Farm",
                "farm_description": "A small family-run organic farm.",
                "farm_postcode": "BS1 4AB",
                "contact_email": "contact@bluecowfarm.com",
                "contact_phone": "07123456789",
                "approved_by_admin": self.admin_user,
                "is_approved": True,
                "approved_at": timezone.now(),
                "payout_method": "BANK_TRANSFER",
                "bank_account_name": "Blue Cow Farm Ltd",
                "bank_account_number": "12345678",
                "bank_sort_code": "12-34-56",
                "organic_certification_number": "ORG-12345",
            }
        )
        self.stdout.write(self.style.SUCCESS("Producer created or reused."))

    # ------------------------------------------------------------
    # CATEGORIES (updated + Certified Organic)
    # ------------------------------------------------------------
    def create_categories(self):
        categories = [
            ("Meat", "Fresh meat products", Decimal("0.00"), "MT"),
            ("Dairy and Eggs", "Milk, cheese, eggs", Decimal("0.00"), "DAE"),
            ("Fruit", "Fresh fruits", Decimal("0.00"), "FR"),
            ("Vegetables", "Fresh vegetables", Decimal("0.00"), "VEG"),
            ("Seasonal Produce", "Seasonal farm goods", Decimal("0.00"), "SEA"),
            ("Certified Organic", "Fully certified organic produce", Decimal("0.00"), "SEA"),
        ]

        self.categories = []

        for name, description, vat, food_group in categories:
            category, _ = self.Category.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "vat": vat,
                    "food_groups": food_group,
                }
            )
            self.categories.append(category)

        self.certified_organic_category = self.Category.objects.get(name="Certified Organic")

        self.stdout.write(self.style.SUCCESS("Categories created or reused."))

    # ------------------------------------------------------------
    # ALLERGENS
    # ------------------------------------------------------------
    def create_allergens(self):
        allergen_codes = [
            "NUT", "SEA", "PEA", "SOY", "MUS", "FSH", "MOL",
            "CRU", "CEL", "GLU", "SUL", "LUP", "EGG", "MLK", "NON"
        ]

        self.allergens = [
            self.Allergen.objects.get_or_create(name=code)[0]
            for code in allergen_codes
        ]

        self.stdout.write(self.style.SUCCESS("Allergens created or reused."))

    # ------------------------------------------------------------
    # PRODUCTS (5 per category)
    # ------------------------------------------------------------
    def create_products(self):
        now = timezone.now()
        expiry = now + timezone.timedelta(days=7)

        product_templates = [
            ("Sample Product A", "Description for product A", Decimal("2.50"), "KG"),
            ("Sample Product B", "Description for product B", Decimal("3.00"), "EA"),
            ("Sample Product C", "Description for product C", Decimal("1.80"), "PK"),
            ("Sample Product D", "Description for product D", Decimal("4.20"), "KG"),
            ("Sample Product E", "Description for product E", Decimal("5.50"), "EA"),
        ]

        for category in self.categories:
            for name, description, price, unit in product_templates:

                product_name = f"{category.name} - {name}"

                self.Product.objects.get_or_create(
                    name=product_name,
                    defaults={
                        "producer": self.producer,
                        "category": category,
                        "moderated_by_admin": self.admin,
                        "description": description,
                        "price": price,
                        "unit": unit,
                        "image": None,
                        "stock_quantity": 100,
                        "low_stock_threshold": 10,
                        "harvest_date": now,
                        "farm_origin": "Blue Cow Farm",
                        "organic_certification_status": "CERTIFIED",
                        "storage_guidance": "Keep refrigerated.",
                        "expiry_date": expiry,
                        "expiry_type": "BB",
                        "availability_status": "AV",
                        "surplus_status": "NN",
                        "surplus_discount_percentage": Decimal("0.00"),
                        "surplus_expiry": now,
                        "surplus_note": None,
                        "status": "PUBLISHED",
                    }
                )

        self.stdout.write(self.style.SUCCESS("5 products created for each category."))

    # ------------------------------------------------------------
    # CERTIFIED ORGANIC PRODUCTS (10 items)
    # ------------------------------------------------------------
    def create_certified_organic_products(self):
        now = timezone.now()
        expiry = now + timezone.timedelta(days=10)

        organic_products = [
            ("Organic Carrots", "Fresh organic carrots", Decimal("1.20"), "KG"),
            ("Organic Apples", "Crisp organic apples", Decimal("2.80"), "EA"),
            ("Organic Spinach", "Leafy organic spinach", Decimal("1.50"), "PK"),
            ("Organic Tomatoes", "Vine-ripened organic tomatoes", Decimal("2.20"), "KG"),
            ("Organic Broccoli", "Fresh organic broccoli", Decimal("1.90"), "EA"),
            ("Organic Strawberries", "Sweet organic strawberries", Decimal("3.50"), "PK"),
            ("Organic Potatoes", "Farm-grown organic potatoes", Decimal("1.10"), "KG"),
            ("Organic Onions", "Organic yellow onions", Decimal("0.90"), "KG"),
            ("Organic Lettuce", "Crisp organic lettuce", Decimal("1.30"), "EA"),
            ("Organic Blueberries", "Fresh organic blueberries", Decimal("3.80"), "PK"),
        ]

        for name, description, price, unit in organic_products:
            self.Product.objects.get_or_create(
                name=name,
                defaults={
                    "producer": self.producer,
                    "category": self.certified_organic_category,
                    "moderated_by_admin": self.admin,
                    "description": description,
                    "price": price,
                    "unit": unit,
                    "image": None,
                    "stock_quantity": 200,
                    "low_stock_threshold": 20,
                    "harvest_date": now,
                    "farm_origin": "Blue Cow Farm",
                    "organic_certification_status": "CERTIFIED",
                    "storage_guidance": "Store in a cool dry place.",
                    "expiry_date": expiry,
                    "expiry_type": "BB",
                    "availability_status": "AV",
                    "surplus_status": "NN",
                    "surplus_discount_percentage": Decimal("0.00"),
                    "surplus_expiry": now,
                    "surplus_note": None,
                    "status": "PUBLISHED",
                }
            )

        self.stdout.write(self.style.SUCCESS("Certified Organic products created."))