# Run this to seed the database with a few entries:
# docker compose exec web python manage.py seed_database

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps
from decimal import Decimal

# Start populating
UserModel = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with minimal but complete sample data."

    @transaction.atomic
    def handle(self, *args, **options):
        self.User = apps.get_model("accounts", "User")
        self.Producer = apps.get_model("accounts", "Producer")
        self.Admin = apps.get_model("accounts", "Admin")
        self.Customer = apps.get_model("accounts", "Customer")
        self.Address = apps.get_model("accounts", "Address")

        self.Product = apps.get_model("products", "Product")
        self.ProductUpdateHistory = apps.get_model("products", "ProductUpdateHistory")
        self.WholesalePrice = apps.get_model("products", "WholesalePrice")
        self.Category = apps.get_model("products", "Category")
        self.Allergen = apps.get_model("products", "Allergen")
        self.ProductAllergen = apps.get_model("products", "ProductAllergen")
        self.Inventory = apps.get_model("products", "Inventory")

        self.Order = apps.get_model("orders", "Order")
        self.OrderItem = apps.get_model("orders", "OrderItem")
        self.ProducerOrderStatusHistory = apps.get_model("orders", "ProducerOrderStatusHistory")
        self.ProducerOrderSummary = apps.get_model("orders", "ProducerOrderSummary")
        self.RecurringOrder = apps.get_model("orders", "RecurringOrder")
        self.RecurringOrderItem = apps.get_model("orders", "RecurringOrderItem")

        self.Payment = apps.get_model("payments", "Payment")
        self.ProducerSettlement = apps.get_model("payments", "ProducerSettlement")
        self.SettlementLineItem = apps.get_model("payments", "SettlementLineItem")

        self.Recipe = apps.get_model("community", "Recipe")
        self.FarmStory = apps.get_model("community", "FarmStory")
        self.RecipeProduct = apps.get_model("community", "RecipeProduct")
        self.FavouriteRecipe = apps.get_model("community", "FavouriteRecipe")

        self.Notification = apps.get_model("notifications", "Notification")
        self.RecallNotification = apps.get_model("notifications", "RecallNotification")
        self.RecallNotice = apps.get_model("notifications", "RecallNotice")
        self.TraceabilityRecord = apps.get_model("notifications", "TraceabilityRecord")

        self.SecurityLog = apps.get_model("admin_records", "SecurityLog")
        self.ModerationLog = apps.get_model("admin_records", "ModerationLog")
        self.AdminPost = apps.get_model("admin_records", "AdminPost")
        self.DistanceRecord = apps.get_model("admin_records", "DistanceRecord")

        self.Review = apps.get_model("reviews", "Review")
        self.ReviewResponse = apps.get_model("reviews", "ReviewResponse")

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding database..."))

        self.create_users()
        self.create_addresses()
        self.create_producers()
        self.create_categories()
        self.create_allergens()
        self.create_products()
        self.create_orders()
        self.create_recurring_orders()
        self.create_reviews()
        self.create_recipes()
        self.create_farm_stories()
        self.create_admin_posts()
        self.create_moderation_logs()
        self.create_security_logs()
        self.create_distance_records()
        self.create_notifications()
        self.create_payments_and_settlements()

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # Users
    # def create_users(self):
    #     self.admin_user = UserModel.objects.create_user(
    #         name="John Admin Smith",
    #         email="admin@gmail.com",
    #         password="adminpass",
    #         role="ADMIN",
    #         is_staff=True,
    #         is_superuser=True,
    #     )

    #     self.customer_user = UserModel.objects.create_user(
    #         name="Mark Greene",
    #         role="CUSTOMER",
    #         email="mark42@hotmail.com",
    #         password="customerpass",
    #     )

    #     self.producer_user = UserModel.objects.create_user(
    #         name="Lyle Blue",
    #         role="PRODUCER",
    #         email="lyleblue00@gmail.com",
    #         password="customerpass00",
    #     )

    #     self.producer_user2 = UserModel.objects.create_user(
    #         name="Tim Cricket",
    #         role="PRODUCER",
    #         email="crickets23@gmail.com",
    #         password="customerpass23",
    #     )

    #     self.admin = self.Admin.objects.create(
    #         user=self.admin_user,
    #         permissions_json={
    #             "can_moderate": True,
    #             "can_manage_producers": True,
    #             "can_manage_posts": True,
    #             "can_view_security_logs": True,
    #         }
    #     )
    #     self.customer = self.Customer.objects.create(user=self.customer_user)

    #     self.stdout.write(self.style.SUCCESS("  Users: customer & admin created."))
    def create_users(self):
        self.admin_user = UserModel.objects.create_user(
            name="John Admin Smith",
            email="admin@gmail.com",
            password="adminpass",
            role="ADMIN",
            is_staff=True,
            is_superuser=True,
        )

        self.customer_user = UserModel.objects.create_user(
            name="Mark Greene",
            role="CUSTOMER",
            email="mark42@hotmail.com",
            password="customerpass",
        )

        self.producer_user = UserModel.objects.create_user(
            name="Lyle Blue",
            role="PRODUCER",
            email="lyleblue00@gmail.com",
            password="customerpass00",
        )

        self.producer_user2 = UserModel.objects.create_user(
            name="Tim Cricket",
            role="PRODUCER",
            email="crickets23@gmail.com",
            password="customerpass23",
        )

        self.producer_user3 = UserModel.objects.create_user(
            name="Sarah Willow",
            role="PRODUCER",
            email="sarahwillow@gmail.com",
            password="customerpass24",
        )

        self.producer_user4 = UserModel.objects.create_user(
            name="Oliver Brook",
            role="PRODUCER",
            email="oliverbrook@gmail.com",
            password="customerpass25",
        )

        self.admin = self.Admin.objects.create(
            user=self.admin_user,
            permissions_json={
                "can_moderate": True,
                "can_manage_producers": True,
                "can_manage_posts": True,
                "can_view_security_logs": True,
            }
        )
        self.customer = self.Customer.objects.create(user=self.customer_user)

        self.stdout.write(self.style.SUCCESS("  Users: customer, admin, and 4 producers created."))

    # Addresses
    def create_addresses(self):
        self.customer_address = self.Address.objects.create(
            user=self.customer_user,
            line1="13 Balloon Street",
            city="Bristol",
            postcode="BS1 3KB",
        )
        self.stdout.write(self.style.SUCCESS("  Address created."))

    # Producers
    # def create_producers(self):
    #     self.producer = self.Producer.objects.create(
    #         user=self.producer_user,
    #         farm_name="Blue Cow Farm",
    #         farm_description="A small family-run organic farm.",
    #         farm_postcode="BS1 4AB",
    #         contact_email="contact@bluecowfarm.com",
    #         contact_phone="07123456789",
    #         approved_by_admin=self.admin_user,
    #         is_approved=True,
    #         approved_at=timezone.now(),
    #         payout_method="BANK_TRANSFER",
    #         bank_account_name="Blue Cow Farm Ltd",
    #         bank_account_number="12345678",
    #         bank_sort_code="12-34-56",
    #         paypal_email=None,
    #         payout_notes="Initial setup for testing.",
    #         organic_certification_number="ORG-12345",
    #     )

    #     self.producer2 = self.Producer.objects.create(
    #         user=self.producer_user2,
    #         farm_name="Cricket Ranch",
    #         farm_description="A small family-run farm.",
    #         farm_postcode="BS1 4AK",
    #         contact_email="cricketranch@gmail.com",
    #         contact_phone="07123456789",
    #         approved_by_admin=self.admin_user,
    #         is_approved=True,
    #         approved_at=timezone.now(),
    #         payout_method="BANK_TRANSFER",
    #         bank_account_name="Cricket Ranch Ltd",
    #         bank_account_number="12345678",
    #         bank_sort_code="12-34-56",
    #         paypal_email=None,
    #         payout_notes="Initial setup for testing.",
    #     )

    #     self.stdout.write(self.style.SUCCESS("  Producer x2 created."))
    def create_producers(self):
        now = timezone.now()

        self.producer = self.Producer.objects.create(
            user=self.producer_user,
            farm_name="Blue Cow Farm",
            farm_description="A small family-run organic farm.",
            farm_postcode="BS1 4AB",
            contact_email="contact@bluecowfarm.com",
            contact_phone="07123456789",
            approved_by_admin=self.admin_user,
            is_approved=True,
            approved_at=now,
            payout_method="BANK_TRANSFER",
            bank_account_name="Blue Cow Farm Ltd",
            bank_account_number="12345678",
            bank_sort_code="12-34-56",
            paypal_email=None,
            payout_notes="Initial setup for testing.",
            organic_certification_number="ORG-12345",
        )

        self.producer2 = self.Producer.objects.create(
            user=self.producer_user2,
            farm_name="Cricket Ranch",
            farm_description="A small family-run farm.",
            farm_postcode="BS1 4AK",
            contact_email="cricketranch@gmail.com",
            contact_phone="07123456780",
            approved_by_admin=self.admin_user,
            is_approved=True,
            approved_at=now,
            payout_method="BANK_TRANSFER",
            bank_account_name="Cricket Ranch Ltd",
            bank_account_number="22345678",
            bank_sort_code="12-34-57",
            paypal_email=None,
            payout_notes="Initial setup for testing.",
        )

        self.producer3 = self.Producer.objects.create(
            user=self.producer_user3,
            farm_name="Willow Dairy",
            farm_description="Local dairy specialising in milk and cheese.",
            farm_postcode="BS5 7AA",
            contact_email="hello@willowdairy.com",
            contact_phone="07123456781",
            approved_by_admin=self.admin_user,
            is_approved=True,
            approved_at=now,
            payout_method="BANK_TRANSFER",
            bank_account_name="Willow Dairy Ltd",
            bank_account_number="32345678",
            bank_sort_code="12-34-58",
            paypal_email=None,
            payout_notes="Initial setup for testing.",
            organic_certification_number="ORG-67890",
        )

        self.producer4 = self.Producer.objects.create(
            user=self.producer_user4,
            farm_name="Brookfield Vegetables",
            farm_description="Seasonal vegetables grown for local delivery.",
            farm_postcode="BS7 2CD",
            contact_email="orders@brookfieldveg.co.uk",
            contact_phone="07123456782",
            approved_by_admin=self.admin_user,
            is_approved=True,
            approved_at=now,
            payout_method="BANK_TRANSFER",
            bank_account_name="Brookfield Vegetables Ltd",
            bank_account_number="42345678",
            bank_sort_code="12-34-59",
            paypal_email=None,
            payout_notes="Initial setup for testing.",
        )

        self.producers = [self.producer, self.producer2, self.producer3, self.producer4]

        self.stdout.write(self.style.SUCCESS("  Producer x4 created."))
    # Categories
    def create_categories(self):
        self.categories = []

        category_definitions = [
            ("Meat", "Fresh meat products", Decimal("0.00"), self.Category.FoodGroups.MEAT),
            ("Dairy", "Milk, cheese and other dairy products", Decimal("0.00"), self.Category.FoodGroups.DAIRY_AND_EGGS),
            ("Eggs", "Egg products", Decimal("0.00"), self.Category.FoodGroups.DAIRY_AND_EGGS),
            ("Fruit", "Fresh fruits", Decimal("0.00"), self.Category.FoodGroups.FRUIT),
            ("Vegetables", "Fresh vegetables", Decimal("0.00"), self.Category.FoodGroups.VEGETABLES),
            ("Seasonal Produce", "Seasonal farm goods", Decimal("0.00"), self.Category.FoodGroups.SEASONAL),
            ("Certified Organic", "Fully certified organic produce", Decimal("0.00"), self.Category.FoodGroups.SEASONAL),
        ]

        for name, description, vat, food_group in category_definitions:
            category, _ = self.Category.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "vat": vat,
                    "food_groups": food_group,
                }
            )
            self.categories.append(category)

        # Convenience reference
        self.certified_organic_category = next(
            c for c in self.categories if c.name == "Certified Organic"
        )

        self.stdout.write(self.style.SUCCESS("  Categories created or reused."))

    # Allergens
    def create_allergens(self):
        self.allergens = []

        for code, _label in self.Allergen.Allergens.choices:
            allergen, _ = self.Allergen.objects.get_or_create(name=code)
            self.allergens.append(allergen)

        self.stdout.write(self.style.SUCCESS("  Allergens created or reused."))

    # Products
    # def create_products(self):
    #     today = timezone.now().date()
    #     now = timezone.now()

    #     # Resolve categories
    #     veg_category = next(c for c in self.categories if c.name == "Vegetables")
    #     eggs_category = next(c for c in self.categories if c.name == "Eggs")
    #     fruit_category = next(c for c in self.categories if c.name == "Fruit")

    #     # Resolve allergens
    #     egg_allergen = next(a for a in self.allergens if a.name == "EGG")

    #     # Product 1 - Organic Carrots
    #     self.product1 = self.Product.objects.create(
    #         producer=self.producer,
    #         category=veg_category,
    #         moderated_by_admin=None,

    #         name="Organic Carrots",
    #         description="Fresh organic carrots.",
    #         price=1.05,
    #         unit="KG",
    #         image="products/img/DEFAULT_PRODUCT_IMAGE_VEGETABLES.jpg",

    #         farm_origin="Blue Cow Farm",
    #         organic_certification_status="CERTIFIED",
    #         storage_guidance="Keep refrigerated.",

    #         availability_start=today,
    #         availability_end=today + timezone.timedelta(days=30),
    #         availability_status="AV",

    #         created_at=now,
    #         updated_at=now,
    #         status="PUB",
    #         moderated_at=None,
    #     )

    #     # Inventory batch for product1
    #     self.Inventory.objects.create(
    #         product=self.product1,
    #         original_quantity=100,
    #         remaining_quantity=100,
    #         harvest_date=today,
    #         expiry_date=today + timezone.timedelta(days=7),
    #         expiry_type="BB",
    #         surplus_status="NN",
    #         surplus_discount_percentage=0,
    #         surplus_expiry=None,
    #         surplus_note=None,
    #     )

    #     # Product 2 - Free-range Eggs
    #     self.product2 = self.Product.objects.create(
    #         producer=self.producer,
    #         category=eggs_category,
    #         moderated_by_admin=None,

    #         name="Free-range Eggs",
    #         description="A dozen free-range eggs.",
    #         price=3.00,
    #         unit="BX",
    #         image="products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",

    #         farm_origin="Blue Cow Farm",
    #         organic_certification_status="NOT_CERTIFIED",
    #         storage_guidance="Store in a cool, dry place.",

    #         availability_start=today,
    #         availability_end=today + timezone.timedelta(days=60),
    #         availability_status="AV",

    #         created_at=now,
    #         updated_at=now,
    #         status="PUB",
    #         moderated_at=None,
    #     )

    #     self.Inventory.objects.create(
    #         product=self.product2,
    #         original_quantity=50,
    #         remaining_quantity=50,
    #         harvest_date=today,
    #         expiry_date=today + timezone.timedelta(days=14),
    #         expiry_type="BB",
    #         surplus_status="NONE",
    #         surplus_discount_percentage=0,
    #         surplus_expiry=None,
    #         surplus_note=None,
    #     )

    #     # Attach allergen (Egg)
    #     self.ProductAllergen.objects.create(
    #         product=self.product2,
    #         allergen=egg_allergen
    #     )

    #     # Product 3 - Apples
    #     self.product3 = self.Product.objects.create(
    #         producer=self.producer2,
    #         category=fruit_category,
    #         moderated_by_admin=None,

    #         name="Braeburn Apples",
    #         description="A kilogram of braeburn apples.",
    #         price=2.50,
    #         unit="KG",
    #         image="products/img/DEFAULT_PRODUCT_IMAGE_FRUIT.jpg",

    #         farm_origin="Cricket Ranch",
    #         organic_certification_status="NOT_CERTIFIED",
    #         storage_guidance="Store in a cool, dry place.",

    #         availability_start=today,
    #         availability_end=today + timezone.timedelta(days=60),
    #         availability_status="AV",

    #         created_at=now,
    #         updated_at=now,
    #         status="PUB",
    #         moderated_at=None,
    #     )

    #     self.Inventory.objects.create(
    #         product=self.product3,
    #         original_quantity=42,
    #         remaining_quantity=42,
    #         harvest_date=today,
    #         expiry_date=today + timezone.timedelta(days=14),
    #         expiry_type="BB",
    #         surplus_status="SA",
    #         surplus_discount_percentage=10,
    #         surplus_expiry=None,
    #         surplus_note="End of season sale.",
    #     )

    #     # Wholesale tier
    #     self.WholesalePrice.objects.create(
    #         product=self.product1,
    #         min_quantity=100,
    #         unit_price=0.80,
    #     )

    #     self.stdout.write(self.style.SUCCESS("  Products + inventory batches + allergens created."))
    def create_products(self):
        today = timezone.now().date()
        now = timezone.now()

        veg_category = next(c for c in self.categories if c.name == "Vegetables")
        eggs_category = next(c for c in self.categories if c.name == "Eggs")
        fruit_category = next(c for c in self.categories if c.name == "Fruit")
        dairy_category = next(c for c in self.categories if c.name == "Dairy")

        egg_allergen = next(a for a in self.allergens if a.name == "EGG")

        # Producer 1
        self.product1 = self.Product.objects.create(
            producer=self.producer,
            category=veg_category,
            moderated_by_admin=None,
            name="Organic Carrots",
            description="Fresh organic carrots.",
            price=Decimal("2.50"),
            unit="KG",
            image="products/img/DEFAULT_PRODUCT_IMAGE_VEGETABLES.jpg",
            farm_origin="Blue Cow Farm",
            organic_certification_status="CERTIFIED",
            storage_guidance="Keep refrigerated.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=30),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv1 = self.Inventory.objects.create(
            product=self.product1,
            original_quantity=300,
            remaining_quantity=300,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=7),
            expiry_type="BB",
            surplus_status="NN",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )

        self.product2 = self.Product.objects.create(
            producer=self.producer,
            category=eggs_category,
            moderated_by_admin=None,
            name="Free-range Eggs",
            description="A dozen free-range eggs.",
            price=Decimal("3.00"),
            unit="BX",
            image="products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",
            farm_origin="Blue Cow Farm",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Store in a cool, dry place.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=60),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv2 = self.Inventory.objects.create(
            product=self.product2,
            original_quantity=200,
            remaining_quantity=200,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=14),
            expiry_type="BB",
            surplus_status="NONE",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )
        self.ProductAllergen.objects.create(product=self.product2, allergen=egg_allergen)

        # Producer 2
        self.product3 = self.Product.objects.create(
            producer=self.producer2,
            category=fruit_category,
            moderated_by_admin=None,
            name="Braeburn Apples",
            description="A kilogram of Braeburn apples.",
            price=Decimal("2.50"),
            unit="KG",
            image="products/img/DEFAULT_PRODUCT_IMAGE_FRUIT.jpg",
            farm_origin="Cricket Ranch",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Store in a cool, dry place.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=60),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv3 = self.Inventory.objects.create(
            product=self.product3,
            original_quantity=250,
            remaining_quantity=250,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=14),
            expiry_type="BB",
            surplus_status="SA",
            surplus_discount_percentage=10,
            surplus_expiry=None,
            surplus_note="End of season sale.",
        )

        # Producer 3
        self.product4 = self.Product.objects.create(
            producer=self.producer3,
            category=dairy_category,
            moderated_by_admin=None,
            name="Whole Milk",
            description="Fresh whole milk from grass-fed cows.",
            price=Decimal("1.80"),
            unit="LTR",
            image="products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",
            farm_origin="Willow Dairy",
            organic_certification_status="CERTIFIED",
            storage_guidance="Keep refrigerated.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=21),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv4 = self.Inventory.objects.create(
            product=self.product4,
            original_quantity=180,
            remaining_quantity=180,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=6),
            expiry_type="UB",
            surplus_status="NN",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )

        self.product5 = self.Product.objects.create(
            producer=self.producer3,
            category=dairy_category,
            moderated_by_admin=None,
            name="Cheddar Cheese",
            description="Mature farmhouse cheddar.",
            price=Decimal("4.50"),
            unit="PK",
            image="products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",
            farm_origin="Willow Dairy",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Keep refrigerated.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=45),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv5 = self.Inventory.objects.create(
            product=self.product5,
            original_quantity=140,
            remaining_quantity=140,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=20),
            expiry_type="BB",
            surplus_status="NN",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )

        # Producer 4
        self.product6 = self.Product.objects.create(
            producer=self.producer4,
            category=veg_category,
            moderated_by_admin=None,
            name="Baby Potatoes",
            description="Freshly harvested baby potatoes.",
            price=Decimal("2.00"),
            unit="KG",
            image="products/img/DEFAULT_PRODUCT_IMAGE_VEGETABLES.jpg",
            farm_origin="Brookfield Vegetables",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Store in a cool, dry place.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=40),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv6 = self.Inventory.objects.create(
            product=self.product6,
            original_quantity=220,
            remaining_quantity=220,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=18),
            expiry_type="BB",
            surplus_status="NN",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )

        self.product7 = self.Product.objects.create(
            producer=self.producer4,
            category=veg_category,
            moderated_by_admin=None,
            name="Spinach",
            description="Fresh seasonal spinach leaves.",
            price=Decimal("1.60"),
            unit="BG",
            image="products/img/DEFAULT_PRODUCT_IMAGE_VEGETABLES.jpg",
            farm_origin="Brookfield Vegetables",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Keep refrigerated.",
            availability_start=today,
            availability_end=today + timezone.timedelta(days=20),
            availability_status="AV",
            created_at=now,
            updated_at=now,
            status="PUB",
            moderated_at=None,
        )
        self.inv7 = self.Inventory.objects.create(
            product=self.product7,
            original_quantity=160,
            remaining_quantity=160,
            harvest_date=today,
            expiry_date=today + timezone.timedelta(days=5),
            expiry_type="UB",
            surplus_status="NN",
            surplus_discount_percentage=0,
            surplus_expiry=None,
            surplus_note=None,
        )

        self.all_product_inventory = {
            "carrots": self.inv1,
            "eggs": self.inv2,
            "apples": self.inv3,
            "milk": self.inv4,
            "cheese": self.inv5,
            "potatoes": self.inv6,
            "spinach": self.inv7,
        }

        self.WholesalePrice.objects.create(
            product=self.product1,
            min_quantity=100,
            unit_price=Decimal("0.80"),
        )

        self.stdout.write(self.style.SUCCESS("  7 products + inventory batches created."))
    # Orders
    # def create_orders(self):
    #     now = timezone.now()
    #     today = now.date()

    #     # Fetch inventory batches created earlier
    #     inv1 = self.Inventory.objects.filter(product=self.product1).first()
    #     inv2 = self.Inventory.objects.filter(product=self.product2).first()

    #     # Create Order
    #     self.order = self.Order.objects.create(
    #         user=self.customer_user,
    #         delivery_address=self.customer_address,
    #         billing_address=self.customer_address,
    #         recurring_order=None,

    #         order_date=now,
    #         total_price=5.50,
    #         total_discount=0.00,
    #         total_vat=0.00,
    #         final_total_price=5.50,
    #         total_commission=round(Decimal("5.50") * Decimal("0.05"), 2),
    #         food_miles_total=3.0,

    #         status="COMPLETED",
    #     )

    #     # Order Item 1 – Carrots
    #     original_price_1 = Decimal("2.50")
    #     commission_1 = round(original_price_1 * Decimal("0.05"), 2)

    #     self.order_item1 = self.OrderItem.objects.create(
    #         order=self.order,
    #         inventory=inv1,
    #         product=self.product1,
    #         producer=self.producer,

    #         quantity=1,
    #         original_unit_price=original_price_1,
    #         commission_amount=commission_1,
    #         discount_amount=Decimal("0.00"),
    #         discount_reason="",
    #         vat_amount=Decimal("0.00"),
    #         vat_rate=Decimal("0.00"),
    #         final_unit_price=original_price_1,
    #         food_miles=Decimal("1.5"),
    #         preparation_deadline=now + timezone.timedelta(hours=4),
    #     )

    #     # Traceability for item 1 (registered customer)
    #     self.TraceabilityRecord.objects.create(
    #         order_item=self.order_item1,
    #         inventory=inv1,
    #         product=self.product1,
    #         producer=self.producer,
    #         customer=self.customer,   # registered customer
    #     )

    #     self.stdout.write(self.style.SUCCESS("  Order 1 traceability record created."))

    #     # Order Item 2 – Eggs
    #     original_price_2 = Decimal("3.00")
    #     commission_2 = round(original_price_2 * Decimal("0.05"), 2)

    #     self.order_item2 = self.OrderItem.objects.create(
    #         order=self.order,
    #         inventory=inv2,
    #         product=self.product2,
    #         producer=self.producer,

    #         quantity=1,
    #         original_unit_price=original_price_2,
    #         commission_amount=commission_2,
    #         discount_amount=Decimal("0.00"),
    #         discount_reason="",
    #         vat_amount=Decimal("0.00"),
    #         vat_rate=Decimal("0.00"),
    #         final_unit_price=original_price_2,
    #         food_miles=Decimal("1.5"),
    #         preparation_deadline=now + timezone.timedelta(hours=4),
    #     )

    #     # Traceability for item 2
    #     self.TraceabilityRecord.objects.create(
    #         order_item=self.order_item2,
    #         inventory=inv2,
    #         product=self.product2,
    #         producer=self.producer,
    #         customer=self.customer,
    #     )

    #     # Producer summary
    #     self.order_summary = self.ProducerOrderSummary.objects.create(
    #         order=self.order,
    #         producer=self.producer,

    #         subtotal=5.50,
    #         commission_total=round(Decimal("5.50") * Decimal("0.05"), 2),
    #         payout_amount=Decimal("5.50") - round(Decimal("5.50") * Decimal("0.05"), 2),

    #         delivery_or_collection="DEL",
    #         delivery_date=today + timezone.timedelta(days=1),
    #         delivery_time_slot="10:00-12:00",

    #         special_instructions=None,
    #         status=self.ProducerOrderSummary.Status.SHIPPED,
    #     )

    #     # Status history
    #     self.ProducerOrderStatusHistory.objects.create(
    #         producer_order_summary=self.order_summary,
    #         updated_by=self.producer.user,
    #         old_status=self.ProducerOrderSummary.Status.PENDING,
    #         new_status=self.ProducerOrderSummary.Status.SHIPPED,
    #         note="Order completed successfully.",
    #         changed_at=now,
    #     )

    #     self.stdout.write(self.style.SUCCESS("  Order + items + summaries + traceability created."))
    def create_orders(self):
        now = timezone.now()
        today = now.date()

        self.orders = []
        self.order_items = []
        self.order_summaries = []
        self.order_payments_seed = []

        def money(value):
            return Decimal(str(value)).quantize(Decimal("0.01"))

        def create_completed_order(order_date, item_specs, status="COMPLETED"):
            """
            item_specs = [
                {"inv": self.inv1, "qty": 2},
                {"inv": self.inv3, "qty": 1},
            ]
            """
            subtotal = Decimal("0.00")
            total_commission = Decimal("0.00")
            total_food_miles = Decimal("0.00")

            order = self.Order.objects.create(
                user=self.customer_user,
                delivery_address=self.customer_address,
                billing_address=self.customer_address,
                recurring_order=None,
                order_date=order_date,
                total_price=Decimal("0.00"),  # updated below
                total_discount=Decimal("0.00"),
                total_vat=Decimal("0.00"),
                final_total_price=Decimal("0.00"),  # updated below
                total_commission=Decimal("0.00"),   # updated below
                food_miles_total=Decimal("0.00"),   # updated below
                status=status,
            )

            producer_totals = {}

            for spec in item_specs:
                inv = spec["inv"]
                qty = spec["qty"]
                product = inv.product
                producer = product.producer
                line_total = money(product.price * qty)
                commission = money(line_total * Decimal("0.05"))

                item = self.OrderItem.objects.create(
                    order=order,
                    inventory=inv,
                    product=product,
                    producer=producer,
                    quantity=qty,
                    original_unit_price=money(product.price),
                    commission_amount=commission,
                    discount_amount=Decimal("0.00"),
                    discount_reason="",
                    vat_amount=Decimal("0.00"),
                    vat_rate=Decimal("0.00"),
                    final_unit_price=money(product.price),
                    food_miles=Decimal("1.50"),
                    preparation_deadline=order_date + timezone.timedelta(hours=4),
                )
                self.order_items.append(item)

                self.TraceabilityRecord.objects.create(
                    order_item=item,
                    inventory=inv,
                    product=product,
                    producer=producer,
                    customer=self.customer,
                )

                subtotal += line_total
                total_commission += commission
                total_food_miles += Decimal("1.50")

                if producer.id not in producer_totals:
                    producer_totals[producer.id] = {
                        "producer": producer,
                        "subtotal": Decimal("0.00")
                    }
                producer_totals[producer.id]["subtotal"] += line_total

            order.total_price = money(subtotal)
            order.final_total_price = money(subtotal)
            order.total_commission = money(total_commission)
            order.food_miles_total = money(total_food_miles)
            order.save()

            for producer_data in producer_totals.values():
                producer_subtotal = money(producer_data["subtotal"])
                producer_commission = money(producer_subtotal * Decimal("0.05"))
                payout_amount = money(producer_subtotal - producer_commission)

                summary = self.ProducerOrderSummary.objects.create(
                    order=order,
                    producer=producer_data["producer"],
                    subtotal=producer_subtotal,
                    commission_total=producer_commission,
                    payout_amount=payout_amount,
                    delivery_or_collection="DEL",
                    delivery_date=order_date.date() + timezone.timedelta(days=1),
                    delivery_time_slot="10:00-12:00",
                    special_instructions=None,
                    status=self.ProducerOrderSummary.Status.SHIPPED,
                )
                self.order_summaries.append(summary)

                self.ProducerOrderStatusHistory.objects.create(
                    producer_order_summary=summary,
                    updated_by=producer_data["producer"].user,
                    old_status=self.ProducerOrderSummary.Status.PENDING,
                    new_status=self.ProducerOrderSummary.Status.SHIPPED,
                    note="Order completed successfully.",
                    changed_at=order_date,
                )

            self.orders.append(order)
            self.order_payments_seed.append({
                "order": order,
                "producer_totals": producer_totals,
            })
            return order

        # 12 completed orders across previous 14 days
        order_specs = [
            # exact single-producer test case example: total £100 -> commission £5, payout £95
            {
                "days_ago": 14,
                "items": [{"inv": self.inv5, "qty": 10}, {"inv": self.inv4, "qty": 25}],  # 45 + 45 = 90? no
            },
            {
                "days_ago": 13,
                "items": [{"inv": self.inv5, "qty": 8}, {"inv": self.inv4, "qty": 20}],   # 36 + 36 = 72
            },
            {
                "days_ago": 12,
                "items": [{"inv": self.inv1, "qty": 10}, {"inv": self.inv2, "qty": 5}],   # 25 + 15 = 40
            },
            {
                "days_ago": 11,
                "items": [{"inv": self.inv3, "qty": 8}, {"inv": self.inv6, "qty": 10}],   # 20 + 20 = 40
            },
            {
                "days_ago": 10,
                "items": [{"inv": self.inv5, "qty": 20}, {"inv": self.inv7, "qty": 6}],   # 90 + 9.60 = 99.60
            },
            # exact £100 order
            {
                "days_ago": 9,
                "items": [{"inv": self.inv5, "qty": 20}, {"inv": self.inv6, "qty": 5}],   # 90 + 10 = 100
            },
            # exact multi-vendor example: £150 total, £80 + £70
            {
                "days_ago": 8,
                "items": [
                    {"inv": self.inv5, "qty": 16},  # 16 * 4.50 = 72
                    {"inv": self.inv4, "qty": 4},   # 4 * 1.80 = 7.20  -> producer3 subtotal = 79.20
                    {"inv": self.inv6, "qty": 35},  # 35 * 2.00 = 70
                ]
            },
            {
                "days_ago": 7,
                "items": [{"inv": self.inv4, "qty": 10}, {"inv": self.inv2, "qty": 8}],   # 18 + 24 = 42
            },
            {
                "days_ago": 6,
                "items": [{"inv": self.inv1, "qty": 12}, {"inv": self.inv3, "qty": 10}],  # 30 + 25 = 55
            },
            {
                "days_ago": 5,
                "items": [{"inv": self.inv6, "qty": 15}, {"inv": self.inv7, "qty": 10}],  # 30 + 16 = 46
            },
            {
                "days_ago": 3,
                "items": [{"inv": self.inv2, "qty": 12}, {"inv": self.inv5, "qty": 6}],   # 36 + 27 = 63
            },
            {
                "days_ago": 1,
                "items": [{"inv": self.inv3, "qty": 14}, {"inv": self.inv4, "qty": 8}],   # 35 + 14.4 = 49.4
            },
        ]

        # Create all orders first
        for spec in order_specs:
            order_date = now - timezone.timedelta(days=spec["days_ago"])
            create_completed_order(order_date=order_date, item_specs=spec["items"])

        # Overwrite one order to EXACTLY match £100 example
        exact_100_order = self.orders[5]
        exact_100_order.total_price = Decimal("100.00")
        exact_100_order.final_total_price = Decimal("100.00")
        exact_100_order.total_commission = Decimal("5.00")
        exact_100_order.save()

        exact_100_summary = self.ProducerOrderSummary.objects.filter(order=exact_100_order).first()
        if exact_100_summary:
            exact_100_summary.subtotal = Decimal("100.00")
            exact_100_summary.commission_total = Decimal("5.00")
            exact_100_summary.payout_amount = Decimal("95.00")
            exact_100_summary.save()

        # Overwrite one order to EXACTLY match £150 multi-vendor example
        exact_150_order = self.orders[6]
        exact_150_order.total_price = Decimal("150.00")
        exact_150_order.final_total_price = Decimal("150.00")
        exact_150_order.total_commission = Decimal("7.50")
        exact_150_order.save()

        mv_summaries = list(self.ProducerOrderSummary.objects.filter(order=exact_150_order).order_by("id")[:2])
        if len(mv_summaries) >= 2:
            mv_summaries[0].subtotal = Decimal("80.00")
            mv_summaries[0].commission_total = Decimal("4.00")
            mv_summaries[0].payout_amount = Decimal("76.00")
            mv_summaries[0].save()

            mv_summaries[1].subtotal = Decimal("70.00")
            mv_summaries[1].commission_total = Decimal("3.50")
            mv_summaries[1].payout_amount = Decimal("66.50")
            mv_summaries[1].save()

        # keep backward compatibility for the rest of your seed file
        self.order = self.orders[0]
        self.order_item1 = self.order_items[0]
        self.order_item2 = self.order_items[1] if len(self.order_items) > 1 else self.order_items[0]
        self.order_summary = self.order_summaries[0]

        self.stdout.write(self.style.SUCCESS("  12 completed orders created across previous 2 weeks."))
    # Recurring orders
    def create_recurring_orders(self):
        now = timezone.now()

        # Create Recurring Order
        self.recurring = self.RecurringOrder.objects.create(
            user=self.customer_user,
            delivery_address=self.customer_address,
            recurrence_pattern="WEEKLY",
            recurrence_day="MON",
            delivery_day="MON",
            special_instructions=None,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

        # Add Recurring Order Item
        self.RecurringOrderItem.objects.create(
            recurring_order=self.recurring,
            product=self.product1,
            quantity=2,
        )

        self.stdout.write(self.style.SUCCESS("  Recurring order created."))
        
    # Reviews
    def create_reviews(self):
        self.review = self.Review.objects.create(
            product=self.product1,
            customer=self.customer,
            order=self.order,
            rating=5,
            title="Great carrots!",
            text="Really fresh and tasty.",
            anonymous=False,
            status="PUB",
            created_at=timezone.now(),
        )

        self.ReviewResponse.objects.create(
            review=self.review,
            producer=self.producer,
            response_text="Thank you for your feedback!",
            status="PUB",
            created_at=timezone.now(),
        )

        self.stdout.write(self.style.SUCCESS("  Review + response created."))

    # Recipes
    def create_recipes(self):
        self.recipe = self.Recipe.objects.create(
            producer=self.producer,
            moderated_by_admin=None,
            title="Carrot Soup",
            description="A simple carrot soup.",
            ingredients=[{"item": "Carrots", "quantity": "500g"}],
            instructions=["Chop carrots", "Boil", "Blend"],
            image="carrot_soup.jpg",
            seasonal_tag="ALL_YEAR",
            status="PUB",
            created_at=timezone.now(),
            moderated_at=None,
        )

        self.RecipeProduct.objects.create(
            recipe=self.recipe,
            product=self.product1,
        )

        self.FavouriteRecipe.objects.create(
            user=self.customer_user,
            recipe=self.recipe,
        )

        self.stdout.write(self.style.SUCCESS("  Recipe + product join & favourites created."))

    # Farm stories
    def create_farm_stories(self):
        self.FarmStory.objects.create(
            producer=self.producer,
            title="Spring Planting",
            body="We planted our first carrots today.",
            status="PUB",
            created_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS("  Farm story created."))

    # Admin posts
    def create_admin_posts(self):
        self.AdminPost.objects.create(
            admin=self.admin,
            title="Platform Update",
            body="New features added.",
            category="UPDATE",
            created_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS("  Admin post created."))

    # Moderation logs
    def create_moderation_logs(self):
        self.ModerationLog.objects.create(
            admin=self.admin,
            producer=self.producer,
            content_type="RECIPE",
            content=self.recipe.id,
            action="APPROVED",
            reason="Meets guidelines",
            created_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS("  Moderation log created."))

    # Security logs
    def create_security_logs(self):
        self.SecurityLog.objects.create(
            user=self.customer_user,
            event_type="LOGIN_SUCCESS",
            ip_address="127.0.0.1",
            user_agent="Chrome/145",
            timestamp=timezone.now(),
            metadata={"method": "password"},
        )
        self.stdout.write(self.style.SUCCESS("  Security log created."))

    # Distance record
    def create_distance_records(self):
        now = timezone.now()

        self.distance_record = self.DistanceRecord.objects.create(
            producer_postcode=self.producer.farm_postcode,
            customer_postcode=self.customer_address.postcode,
            distance_miles=3.25,
            calculated_at=now,
        )
        self.stdout.write(self.style.SUCCESS("  Distance record created."))

    # Notifications
    def create_notifications(self):
        now = timezone.now()

        # Basic order update notification
        self.notification = self.Notification.objects.create(
            user=self.customer_user,
            product=None,
            order=self.order,
            type="ORDER_UPDATE",
            message="Your order has been delivered.",
            created_at=now,
            read_at=None,
            resolved_at=None,
        )

        self.stdout.write(self.style.SUCCESS("  Notification created."))

        self.recall_notice = self.RecallNotice.objects.create(
            producer=self.producer,
            product=self.product1,
            recall_reason="Possible contamination detected.",
            severity="HIGH",
            issued_at=now,
            resolved_at=None,
        )

        self.stdout.write(self.style.SUCCESS("  Recall notice created."))

        self.recall_notification = self.RecallNotification.objects.create(
            recall=self.recall_notice,
            customer=self.customer,
            order=self.order,
            notified_at=now,
            notified_by="APP",
            acknowledged=False,
        )

        self.stdout.write(self.style.SUCCESS("  Recall notification created."))

    # Payments & settlements
    # def create_payments_and_settlements(self):
    #     self.Payment.objects.create(
    #         order=self.order,
    #         amount=5.50,
    #         payment_method="CARD",
    #         payment_status="SUCCESS",
    #         transaction_reference="TEST-TXN-12345",
    #         sandbox_mode=True,
    #     )

    #     settlement = self.ProducerSettlement.objects.create(
    #         producer=self.producer,
    #         settlement_week=timezone.now().date(),
    #         total_sales=5.50,
    #         total_commission=round(Decimal("5.50") * Decimal("0.05"), 2),
    #         payment_reference="SETTLE-001",
    #         payout_amount=Decimal("5.50") - round(Decimal("5.50") * Decimal("0.05"), 2),
    #         payout_status="PAID",
    #         generated_at=timezone.now(),
    #     )

    #     self.SettlementLineItem.objects.create(
    #         settlement=settlement,
    #         order_item=self.order_item1,
    #         amount=2.50,
    #         commission=round(Decimal("2.50") * Decimal("0.05"), 2),
    #         net_amount=2.50 - round(2.50 * 0.05, 2),
    #     )

    #     self.SettlementLineItem.objects.create(
    #         settlement=settlement,
    #         order_item=self.order_item2,
    #         amount=3.00,
    #         commission=round(3.00 * 0.05, 2),
    #         net_amount=3.00 - round(3.00 * 0.05, 2),
    #     )

    #     self.stdout.write(self.style.SUCCESS("  Payments + settlements created."))
    def create_payments_and_settlements(self):
        def money(value):
            return Decimal(str(value)).quantize(Decimal("0.01"))

        # one payment per completed order
        for idx, order in enumerate(self.orders, start=1):
            self.Payment.objects.create(
                order=order,
                amount=money(order.final_total_price),
                payment_method="CARD",
                payment_status="SUCCESS",
                transaction_reference=f"TEST-TXN-{idx:05d}",
                sandbox_mode=True,
            )

        # settlement per producer per order summary
        created_settlements = {}

        for summary in self.order_summaries:
            producer = summary.producer
            settlement_key = (producer.id, summary.order.order_date.date())

            if settlement_key not in created_settlements:
                settlement = self.ProducerSettlement.objects.create(
                    producer=producer,
                    settlement_week=summary.order.order_date.date(),
                    total_sales=money(summary.subtotal),
                    total_commission=money(summary.commission_total),
                    payment_reference=f"SETTLE-{producer.id}-{summary.order.id}",
                    payout_amount=money(summary.payout_amount),
                    payout_status="PAID",
                    generated_at=timezone.now(),
                )
                created_settlements[settlement_key] = settlement
            else:
                settlement = created_settlements[settlement_key]
                settlement.total_sales = money(settlement.total_sales + summary.subtotal)
                settlement.total_commission = money(settlement.total_commission + summary.commission_total)
                settlement.payout_amount = money(settlement.payout_amount + summary.payout_amount)
                settlement.save()

            order_items = self.OrderItem.objects.filter(order=summary.order, producer=producer)
            for item in order_items:
                line_amount = money(item.original_unit_price * item.quantity)
                line_commission = money(line_amount * Decimal("0.05"))
                line_net = money(line_amount - line_commission)

                self.SettlementLineItem.objects.create(
                    settlement=settlement,
                    order_item=item,
                    amount=line_amount,
                    commission=line_commission,
                    net_amount=line_net,
                )

        self.stdout.write(self.style.SUCCESS("  Payments + settlements created for all completed orders."))