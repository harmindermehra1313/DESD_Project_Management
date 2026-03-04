from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps

UserModel = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with users, producer, categories, allergens, and products."

    @transaction.atomic
    def handle(self, *args, **options):
        # Load models
        self.User = apps.get_model("accounts", "User")
        self.Producer = apps.get_model("accounts", "Producer")
        self.Admin = apps.get_model("accounts", "Admin")
        self.Customer = apps.get_model("accounts", "Customer")
        self.Address = apps.get_model("accounts", "Address")

        self.Category = apps.get_model("products", "Category")
        self.Allergen = apps.get_model("products", "Allergen")
        self.Product = apps.get_model("products", "Product")

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding database..."))

        self.create_users()
        self.create_addresses()
        self.create_producers()
        self.create_categories()
        self.create_allergens()
        self.create_products()

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
    # CATEGORIES
    # ------------------------------------------------------------
    def create_categories(self):
        categories = [
            ("Vegetables", "Fresh produce", "0.0"),
            ("Fruits", "Fresh fruits and berries", "0.0"),
            ("Dairy", "Milk, cheese, butter", "0.0"),
            ("Meat & Poultry", "Fresh meat and poultry", "0.0"),
            ("Fish & Seafood", "Fresh fish and shellfish", "0.0"),
            ("Bakery", "Bread and baked goods", "0.0"),
            ("Grains & Cereals", "Rice, pasta, oats", "0.0"),
            ("Herbs & Spices", "Fresh herbs and dried spices", "0.0"),
            ("Frozen Foods", "Frozen produce and meals", "0.0"),
            ("Pantry & Dry Goods", "Tinned foods, oils, condiments", "0.0"),
            ("Beverages", "Juices, teas, coffees", "0.0"),
            ("Snacks", "Crisps, nuts, bars", "20.0"),
            ("Confectionery", "Sweets and chocolates", "20.0"),
            ("Eggs", "Farm eggs", "0.0"),
            ("Honey & Preserves", "Honey, jams, chutneys", "0.0"),
            ("Prepared Foods", "Ready meals and prepared dishes", "20.0"),
            ("Artisan Goods", "Handmade and local artisan foods", "0.0"),
        ]

        self.categories = []

        for name, description, vat in categories:
            category, _ = self.Category.objects.get_or_create(
                name=name,
                defaults={"description": description, "vat": vat}
            )
            self.categories.append(category)

        self.stdout.write(self.style.SUCCESS("Categories created or reused."))

    # ------------------------------------------------------------
    # ALLERGENS
    # ------------------------------------------------------------
    def create_allergens(self):
        allergen_names = ["Eggs", "Milk", "Nuts", "Soya", "Sesame"]

        self.allergens = [
            self.Allergen.objects.get_or_create(name=name)[0]
            for name in allergen_names
        ]

        self.stdout.write(self.style.SUCCESS("Allergens created or reused."))

    # ------------------------------------------------------------
    # PRODUCTS (5 per category)
    # ------------------------------------------------------------
    def create_products(self):
        today = timezone.now().date()
        now = timezone.now()

        product_templates = [
            ("Sample Product A", "Description for product A", 2.50, "KG", "sample1.jpg"),
            ("Sample Product B", "Description for product B", 3.00, "EACH", "sample2.jpg"),
            ("Sample Product C", "Description for product C", 1.80, "PACK", "sample3.jpg"),
            ("Sample Product D", "Description for product D", 4.20, "KG", "sample4.jpg"),
            ("Sample Product E", "Description for product E", 5.50, "EACH", "sample5.jpg"),
        ]

        for category in self.categories:
            for name, description, price, unit, image in product_templates:

                product_name = f"{category.name} - {name}"

                self.Product.objects.get_or_create(
                    name=product_name,
                    defaults={
                        "producer": self.producer,
                        "category": category,
                        "description": description,
                        "price": price,
                        "unit": unit,
                        "image": image,
                        "stock_quantity": 100,
                        "low_stock_threshold": 10,
                        "harvest_date": today,
                        "farm_origin": "Blue Cow Farm",
                        "organic_certification_status": "CERTIFIED",
                        "storage_guidance": "Keep refrigerated.",
                        "expiry_date": today + timezone.timedelta(days=7),
                        "expiry_type": "BEST BEFORE",
                        "availability_start": today,
                        "availability_end": today + timezone.timedelta(days=30),
                        "availability_status": "AVAILABLE",
                        "surplus_status": "NONE",
                        "surplus_discount_percentage": 0.00,
                        "created_at": now,
                        "updated_at": now,
                        "status": "PUBLISHED",
                    }
                )

        self.stdout.write(self.style.SUCCESS("5 products created for each category."))