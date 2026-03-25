"""
Seed database with a large, realistic dataset for forecasting and feature testing.

SUMMARY
=======

This script:
- WIPES all existing data in a dependency-safe order.
- POPULATES all major tables across accounts, products, orders, payments, notifications,
  community, reviews, and admin_records.
- EXPORTS all created users (email, password, role) to seeded_users.csv.

DATA VOLUMES (approximate)
==========================

Accounts:
- User:            1 admin + 100 producers + 500 customers  (~601)
- Producer:        100
- Customer:        500
- Admin:           1
- Address:         100 producer addresses + 500 customer addresses (~600)

Products:
- Category:        6 (Vegetables, Fruit, Dairy, Eggs, Meat, Seasonal)
- Allergen:        All choices from Allergen.Allergens
- Product:         100 producers * 10 products each = 1000
- ProductAllergen: ~30% of products get 1 allergen
- Inventory:       1 batch per product = 1000
- InventoryUpdateHistory:
    - Surplus started / ended events for surplus batches
    - Stock-to-zero events
    - Recall-driven status changes
    - Expiry-approaching events (for near-expiry batches)
- WholesalePrice:  (not heavily used here; can be extended if needed)

Orders:
- Order:           ~5000 (with realistic timestamps over the last year)
- OrderItem:       1–5 items per order (skipping some zero-stock inventory)
- ProducerOrderSummary:
    - 1 per producer per order (multi-producer orders supported)
    - Includes address snapshot, payout, commission, delivery info
- ProducerOrderStatusHistory:
    - Multiple entries per summary simulating realistic progression:
      PENDING → PREPARING → PACKAGED → SHIPPED → COMPLETED
- RecurringOrder:
    - A small subset of customers get recurring orders (weekly/fortnightly)
- RecurringOrderItem:
    - 1–3 items per recurring order
- Some Orders are linked back to RecurringOrder via recurring_order FK.

Payments:
- Payment:
    - 1 per order, status COMPLETED, realistic paid_at timestamps
- ProducerSettlement:
    - 1 per producer per order (simple per-order settlement)
- SettlementLineItem:
    - 1 per producer per order, linked to ProducerOrderSummary

Notifications & Recalls:
- RecallNotice:
    - 5 products with existing orders are recalled
    - Recalled products are removed from sale:
      Product.status = "RMV", Product.availability_status = "DIS"
- RecallNotification:
    - For customers who bought recalled products
- Notification:
    - RECALL notifications for recalled products
    - ORDER_UPDATE notifications for a subset of orders
- TraceabilityRecord:
    - 1 per OrderItem, linking inventory, product, producer, customer

Community:
- Recipe:
    - 1–3 per producer, moderated by admin, seasonal tags
- RecipeProduct:
    - 2–5 products per recipe
- FarmStory:
    - 1–2 per producer
- FavouriteRecipe:
    - Random customers favourite random recipes (unique per user/recipe)

Reviews:
- Review:
    - 1–3 reviews for a subset of products that have orders
- ReviewResponse:
    - ~40% of reviews get a producer response

Admin Records:
- SecurityLog:
    - ~200 events across random users
- AdminPost:
    - ~10 posts (announcements, updates, etc.)
- ModerationLog:
    - ~50 moderation actions across content types
- DistanceRecord:
    - ~200 producer/customer postcode pairs with distances

Rules & Behaviour
=================

- Customer purchase patterns:
    - Profiles: weekly, monthly, seasonal, loyal_producer, category_heavy, light
    - Weekly: more recent orders, weekend bias
    - Monthly: spread over the year
    - Category-heavy: larger baskets focused on certain categories
    - Loyal_producer: tends to buy from the same producer
    - Seasonal: fruit in summer/autumn, veg in winter, etc.

- Producer-specific behaviour:
    - Each producer is assigned a type: veg, fruit, dairy, meat, eggs, seasonal
    - Fruit producers: more orders in summer/autumn
    - Veg producers: more orders in colder months
    - Meat producers: weekend spikes
    - Dairy/eggs: steady demand

- Inventory & surplus:
    - Each product has one inventory batch
    - Some batches have 0 remaining_quantity
    - Some batches have surplus_status:
        - NN (None)
        - SA (Surplus Active)
        - SE (Surplus Expired)
    - Surplus discount is random between 10% and 90%
    - InventoryUpdateHistory:
        - reduction_started for SA
        - reduction_ended for SE
        - field_change when remaining_quantity hits 0
        - field_change when product is recalled (status change)
        - field_change for near-expiry batches

- Orders & status progression:
    - Order.status ends as COMPLETED (CMP)
    - ProducerOrderSummary.status progresses:
        PENDING → PREPARING → PACKAGED → SHIPPED → COMPLETED
    - ProducerOrderStatusHistory records each transition with realistic timestamps
    - Timestamps:
        - PENDING at order_date
        - PREPARING ~+1 hour
        - PACKAGED ~+2 hours
        - SHIPPED ~+4 hours
        - COMPLETED ~+6–10 hours

- Recalls:
    - 5 products with existing orders are recalled
    - All recalled products:
        - Product.status = "RMV"
        - Product.availability_status = "DIS"
    - RecallNotice created per product
    - RecallNotification + Notification created for affected customers
    - InventoryUpdateHistory entry for recall status change

- CSV export:
    - All created users (admin, producers, customers) are written to seeded_users.csv
    - Columns: email, password, role
    - Passwords are random but stored in CSV for development use only.

Run with:
    python manage.py seed_database
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps
from decimal import Decimal
import random
import csv
from faker import Faker

fake = Faker("en_GB")
UserModel = get_user_model()

# Dataset size (Large)
NUM_PRODUCERS = 100
NUM_CUSTOMERS = 500
NUM_PRODUCTS_PER_PRODUCER = 10
NUM_ORDERS = 5000

class Command(BaseCommand):
    help = "Wipes and seeds the database with a large, realistic dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        self.load_models()
        self.stdout.write(self.style.MIGRATE_HEADING("Wiping existing data..."))
        self.wipe_database()
        self.stdout.write(self.style.SUCCESS("[✓] Database cleared"))

        self.seeded_users = []  # for CSV export: list of dicts {email, password, role}

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding core accounts..."))
        self.create_admin()
        self.create_customers()
        self.create_producers()
        self.stdout.write(self.style.SUCCESS("[✓] Admin, customers, and producers created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding catalog (categories, allergens, products, inventory)..."))
        self.create_categories()
        self.create_allergens()
        self.create_products_and_inventory()
        self.stdout.write(self.style.SUCCESS("[✓] Categories, allergens, products, inventory, and inventory history created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding recurring orders..."))
        self.create_recurring_orders()
        self.stdout.write(self.style.SUCCESS("[✓] Recurring orders and items created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding orders, summaries, payments, settlements..."))
        self.create_orders_with_patterns()
        self.stdout.write(self.style.SUCCESS("[✓] Orders, order items, summaries, status history, payments, settlements created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding notifications, recalls, traceability..."))
        self.create_recalls_and_notifications()
        self.stdout.write(self.style.SUCCESS("[✓] Notifications, recalls, traceability records created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding community content (recipes, stories, favourites)..."))
        self.create_community_content()
        self.stdout.write(self.style.SUCCESS("[✓] Recipes, recipe links, farm stories, favourites created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding reviews and admin logs..."))
        self.create_reviews()
        self.create_admin_logs()
        self.stdout.write(self.style.SUCCESS("[✓] Reviews, security logs, admin posts, moderation logs, distance records created"))

        self.stdout.write(self.style.MIGRATE_HEADING("Exporting users to CSV..."))
        self.export_users_csv()
        self.stdout.write(self.style.SUCCESS("[✓] Users exported to seeded_users.csv"))

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # ---------------------------------------------------------
    # Load models
    # ---------------------------------------------------------
    def load_models(self):
        # accounts
        self.User = apps.get_model("accounts", "User")
        self.Producer = apps.get_model("accounts", "Producer")
        self.Customer = apps.get_model("accounts", "Customer")
        self.Admin = apps.get_model("accounts", "Admin")
        self.Address = apps.get_model("accounts", "Address")

        # products
        self.Category = apps.get_model("products", "Category")
        self.Product = apps.get_model("products", "Product")
        self.Inventory = apps.get_model("products", "Inventory")
        self.InventoryUpdateHistory = apps.get_model("products", "InventoryUpdateHistory")
        self.WholesalePrice = apps.get_model("products", "WholesalePrice")
        self.Allergen = apps.get_model("products", "Allergen")
        self.ProductAllergen = apps.get_model("products", "ProductAllergen")

        # orders
        self.Order = apps.get_model("orders", "Order")
        self.OrderItem = apps.get_model("orders", "OrderItem")
        self.ProducerOrderSummary = apps.get_model("orders", "ProducerOrderSummary")
        self.ProducerOrderStatusHistory = apps.get_model("orders", "ProducerOrderStatusHistory")
        self.RecurringOrder = apps.get_model("orders", "RecurringOrder")
        self.RecurringOrderItem = apps.get_model("orders", "RecurringOrderItem")

        # payments
        self.Payment = apps.get_model("payments", "Payment")
        self.ProducerSettlement = apps.get_model("payments", "ProducerSettlement")
        self.SettlementLineItem = apps.get_model("payments", "SettlementLineItem")

        # notifications
        self.Notification = apps.get_model("notifications", "Notification")
        self.RecallNotice = apps.get_model("notifications", "RecallNotice")
        self.RecallNotification = apps.get_model("notifications", "RecallNotification")
        self.TraceabilityRecord = apps.get_model("notifications", "TraceabilityRecord")

        # community
        self.Recipe = apps.get_model("community", "Recipe")
        self.RecipeProduct = apps.get_model("community", "RecipeProduct")
        self.FarmStory = apps.get_model("community", "FarmStory")
        self.FavouriteRecipe = apps.get_model("community", "FavouriteRecipe")

        # reviews
        self.Review = apps.get_model("reviews", "Review")
        self.ReviewResponse = apps.get_model("reviews", "ReviewResponse")

        # admin_records
        self.SecurityLog = apps.get_model("admin_records", "SecurityLog")
        self.ModerationLog = apps.get_model("admin_records", "ModerationLog")
        self.AdminPost = apps.get_model("admin_records", "AdminPost")
        self.DistanceRecord = apps.get_model("admin_records", "DistanceRecord")

    # ---------------------------------------------------------
    # Wipe database
    # ---------------------------------------------------------
    def wipe_database(self):
        # Children → parents
        self.TraceabilityRecord.objects.all().delete()
        self.RecallNotification.objects.all().delete()
        self.RecallNotice.objects.all().delete()
        self.Notification.objects.all().delete()

        self.SettlementLineItem.objects.all().delete()
        self.ProducerSettlement.objects.all().delete()
        self.Payment.objects.all().delete()

        self.ProducerOrderStatusHistory.objects.all().delete()
        self.ProducerOrderSummary.objects.all().delete()
        self.OrderItem.objects.all().delete()
        self.Order.objects.all().delete()

        self.RecurringOrderItem.objects.all().delete()
        self.RecurringOrder.objects.all().delete()

        self.InventoryUpdateHistory.objects.all().delete()
        self.Inventory.objects.all().delete()
        self.WholesalePrice.objects.all().delete()
        self.ProductAllergen.objects.all().delete()
        self.Product.objects.all().delete()
        self.Category.objects.all().delete()
        self.Allergen.objects.all().delete()

        self.FavouriteRecipe.objects.all().delete()
        self.RecipeProduct.objects.all().delete()
        self.Recipe.objects.all().delete()
        self.FarmStory.objects.all().delete()

        self.ReviewResponse.objects.all().delete()
        self.Review.objects.all().delete()

        self.SecurityLog.objects.all().delete()
        self.ModerationLog.objects.all().delete()
        self.AdminPost.objects.all().delete()
        self.DistanceRecord.objects.all().delete()

        self.Address.objects.all().delete()
        self.Admin.objects.all().delete()
        self.Producer.objects.all().delete()
        self.Customer.objects.all().delete()
        self.User.objects.all().delete()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def create_user_with_password(self, name, email, role):
        password = fake.password(length=12)
        user = UserModel.objects.create_user(
            name=name,
            email=email,
            password=password,
            role=role,
            phone=fake.phone_number(),
        )
        self.seeded_users.append({"email": email, "password": password, "role": role})
        return user

    def random_money(self, low, high):
        return Decimal(str(random.uniform(low, high))).quantize(Decimal("0.01"))

    def random_discount(self):
        # 10%–90%, 2 decimal places
        value = random.uniform(10, 90)
        return Decimal(str(value)).quantize(Decimal("0.01"))

    # ---------------------------------------------------------
    # Admin
    # ---------------------------------------------------------
    def create_admin(self):
        admin_email = "admin@example.com"
        admin_password = fake.password(length=14)
        admin_user = UserModel.objects.create_superuser(
            email=admin_email,
            password=admin_password,
            name="Platform Admin",
        )
        self.seeded_users.append({"email": admin_email, "password": admin_password, "role": "ADMIN"})

        self.admin = self.Admin.objects.create(
            user=admin_user,
            permissions_json={
                "can_moderate": True,
                "can_manage_producers": True,
                "can_manage_posts": True,
                "can_view_security_logs": True,
            },
        )

    # ---------------------------------------------------------
    # Customers + addresses + purchase profiles
    # ---------------------------------------------------------
    def create_customers(self):
        self.customers = []
        self.customer_profiles = {}  # customer.id -> profile

        profile_types = ["weekly", "monthly", "seasonal", "loyal_producer", "category_heavy", "light"]

        for _ in range(NUM_CUSTOMERS):
            user = self.create_user_with_password(
                name=fake.name(),
                email=fake.unique.email(),
                role="CUSTOMER",
            )
            customer = self.Customer.objects.create(user=user)
            # address
            addr = self.Address.objects.create(
                user=user,
                line1=fake.street_address(),
                city=fake.city(),
                postcode=fake.postcode(),
                is_default_delivery=True,
                is_default_billing=True,
            )
            profile = random.choice(profile_types)
            self.customer_profiles[customer.id] = profile
            self.customers.append(customer)

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.customers)} customers with addresses and profiles"))

    # ---------------------------------------------------------
    # Producers + addresses
    # ---------------------------------------------------------
    def create_producers(self):
        self.producers = []

        FARM_DESCRIPTIONS = [
            "A family‑run farm dedicated to sustainable growing practices.",
            "Known for fresh, locally sourced produce grown with care.",
            "A small independent farm specialising in seasonal vegetables.",
            "Proud producers of high‑quality dairy and free‑range goods.",
            "Committed to ethical farming and environmentally friendly methods.",
            "A community‑focused farm supplying fresh produce all year round.",
            "Experts in traditional farming with a modern sustainable approach.",
            "A countryside farm offering naturally grown fruit and vegetables.",
            "Producers of organic, eco‑friendly, and responsibly sourced foods.",
            "A long‑established farm known for exceptional quality and freshness.",
            "Focused on regenerative agriculture and soil‑first growing.",
            "A trusted local supplier of fresh meat, dairy, and produce.",
            "A modern farm blending innovation with traditional growing methods.",
            "Producers of premium free‑range eggs and farm‑fresh goods.",
            "A small‑batch farm passionate about flavour, quality, and freshness.",
        ]

        for _ in range(NUM_PRODUCERS):
            user = self.create_user_with_password(
                name=fake.name(),
                email=fake.unique.email(),
                role="PRODUCER",
            )

            producer = self.Producer.objects.create(
                user=user,
                farm_name=fake.company(),
                farm_description=random.choice(FARM_DESCRIPTIONS),
                farm_postcode=fake.postcode(),
                contact_email=user.email,
                contact_phone=user.phone,
                approved_by_admin=self.admin.user,
                is_approved=True,
                approved_at=timezone.now(),
                payout_method="BT",
                bank_account_name=fake.company(),
                bank_account_number=str(fake.random_number(8)),
                bank_sort_code="12-34-56",
                paypal_email=None,
                payout_notes="Seeded producer",
            )

            # default address for producer
            self.Address.objects.create(
                user=user,
                line1=fake.street_address(),
                city=fake.city(),
                postcode=producer.farm_postcode,
                is_default_delivery=True,
                is_default_billing=True,
            )

            self.producers.append(producer)

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.producers)} producers with addresses"))

    # ---------------------------------------------------------
    # Categories + allergens
    # ---------------------------------------------------------
    def create_categories(self):
        self.categories = []

        definitions = [
            ("Vegetables", "Fresh vegetables"),
            ("Fruit", "Fresh fruit"),
            ("Dairy", "Milk and cheese"),
            ("Eggs", "Egg products"),
            ("Meat", "Fresh meat"),
            ("Seasonal", "Seasonal produce"),
        ]

        for name, desc in definitions:
            cat, _ = self.Category.objects.get_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "vat": Decimal("0.00"),
                    "food_groups": self.Category.FoodGroups.SEASONAL,
                },
            )
            self.categories.append(cat)

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.categories)} categories"))

    def create_allergens(self):
        self.allergens = []
        for code, _label in self.Allergen.Allergens.choices:
            allergen, _ = self.Allergen.objects.get_or_create(name=code)
            self.allergens.append(allergen)
        self.stdout.write(self.style.SUCCESS(f"[✓] Created/reused {len(self.allergens)} allergens"))

    # ---------------------------------------------------------
    # Products + inventory (with surplus + zero stock + history)
    # ---------------------------------------------------------
    def create_products_and_inventory(self):
        self.all_inventory = []
        self.products = []

        PRODUCT_NAMES = {
            "Vegetables": [
                "Carrots", "Broccoli", "Spinach", "Potatoes", "Onions",
                "Kale", "Leeks", "Cauliflower", "Courgettes", "Cabbage"
            ],
            "Fruit": [
                "Strawberries", "Blueberries", "Apples", "Pears",
                "Raspberries", "Plums", "Cherries", "Blackberries", "Grapes"
            ],
            "Dairy": [
                "Whole Milk", "Cheddar Cheese", "Greek Yogurt",
                "Butter", "Cream", "Cottage Cheese", "Mozzarella"
            ],
            "Eggs": [
                "Free‑Range Eggs", "Organic Eggs", "Duck Eggs", "Quail Eggs"
            ],
            "Meat": [
                "Chicken Breast", "Pork Chops", "Beef Mince",
                "Lamb Shoulder", "Sausages", "Bacon", "Steak"
            ],
            "Seasonal": [
                "Pumpkins", "Brussels Sprouts", "Asparagus",
                "Wild Garlic", "Elderflower", "Rhubarb", "Sweetcorn"
            ],
        }

        CATEGORY_DEFAULT_IMAGES = {
            "Vegetables": "products/img/DEFAULT_PRODUCT_IMAGE_VEGETABLES.jpg",
            "Fruit": "products/img/DEFAULT_PRODUCT_IMAGE_FRUIT.jpg",
            "Dairy": "products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",
            "Eggs": "products/img/DEFAULT_PRODUCT_IMAGE_DAIRY_AND_EGGS.jpg",
            "Meat": "products/img/DEFAULT_PRODUCT_IMAGE_MEAT.jpg",
            "Seasonal": "products/img/DEFAULT_PRODUCT_IMAGE_SEASONAL.jpg",
        }

        DESCRIPTIONS = [
            "Freshly harvested from the farm.",
            "Locally sourced and full of flavour.",
            "Perfect for family meals and weekly cooking.",
            "Grown sustainably using eco‑friendly methods.",
            "A customer favourite known for its quality.",
            "Picked at peak ripeness for maximum taste.",
        ]

        category_cycle = ["Vegetables", "Fruit", "Dairy", "Eggs", "Meat", "Seasonal"]
        category_map = {c.name: c for c in self.categories}

        for idx, producer in enumerate(self.producers):
            for _ in range(NUM_PRODUCTS_PER_PRODUCER):
                cat_name = category_cycle[(idx + random.randint(0, 5)) % len(category_cycle)]
                category = category_map[cat_name]

                price = self.random_money(1.0, 20.0)
                product = self.Product.objects.create(
                    producer=producer,
                    category=category,
                    moderated_by_admin=None,
                    name=random.choice(PRODUCT_NAMES[category.name]),
                    description=random.choice(DESCRIPTIONS),
                    price=price,
                    unit=random.choice(["KG", "EA", "PK", "BX"]),
                    image=CATEGORY_DEFAULT_IMAGES.get(category.name, None),
                    farm_origin=producer.farm_name,
                    organic_certification_status=random.choice(["CERTIFIED", "NOT_CERTIFIED"]),
                    storage_guidance=fake.sentence(),
                    availability_start=timezone.now(),
                    availability_end=timezone.now() + timezone.timedelta(days=90),
                    availability_status="AV",
                    status="PUB",
                )

                # random allergen assignment (optional)
                if random.random() < 0.3:
                    allergen = random.choice(self.allergens)
                    self.ProductAllergen.objects.create(product=product, allergen=allergen)

                # inventory batch
                original_qty = random.randint(50, 500)
                remaining = random.choice([0, random.randint(1, original_qty)])
                surplus_status = random.choice(["NN", "SA", "SE"])
                surplus_discount = None
                surplus_expiry = None
                surplus_note = None
                if surplus_status in ["SA", "SE"]:
                    surplus_discount = self.random_discount()
                    surplus_expiry = timezone.now() + timezone.timedelta(days=random.randint(1, 10))
                    surplus_note = "Seeded surplus"

                inv = self.Inventory.objects.create(
                    product=product,
                    user=producer.user,
                    original_quantity=original_qty,
                    remaining_quantity=remaining,
                    harvest_date=timezone.now().date() - timezone.timedelta(days=random.randint(0, 10)),
                    expiry_date=timezone.now().date() + timezone.timedelta(days=random.randint(3, 30)),
                    expiry_type=random.choice(["BB", "UB"]),
                    surplus_status=surplus_status,
                    surplus_discount_percentage=surplus_discount,
                    surplus_expiry=surplus_expiry,
                    surplus_note=surplus_note,
                )

                # Inventory history: surplus events
                if surplus_status == "SA":
                    self.InventoryUpdateHistory.objects.create(
                        inventory=inv,
                        user=producer.user,
                        field_changed="surplus_status",
                        old_value="NN",
                        new_value="SA",
                        event_type="reduction_started",
                        ended_reason=None,
                        snapshot_discount=surplus_discount,
                        snapshot_expiry=surplus_expiry,
                        snapshot_note=surplus_note,
                    )
                elif surplus_status == "SE":
                    self.InventoryUpdateHistory.objects.create(
                        inventory=inv,
                        user=producer.user,
                        field_changed="surplus_status",
                        old_value="SA",
                        new_value="SE",
                        event_type="reduction_ended",
                        ended_reason="expired",
                        snapshot_discount=surplus_discount,
                        snapshot_expiry=surplus_expiry,
                        snapshot_note=surplus_note,
                    )

                # Inventory history: stock hits zero
                if remaining == 0:
                    self.InventoryUpdateHistory.objects.create(
                        inventory=inv,
                        user=producer.user,
                        field_changed="remaining_quantity",
                        old_value=str(original_qty),
                        new_value="0",
                        event_type="field_change",
                        ended_reason=None,
                        snapshot_discount=surplus_discount,
                        snapshot_expiry=surplus_expiry,
                        snapshot_note="Stock depleted",
                    )

                # Inventory history: near expiry
                days_to_expiry = (inv.expiry_date - timezone.now().date()).days
                if days_to_expiry <= 3:
                    self.InventoryUpdateHistory.objects.create(
                        inventory=inv,
                        user=producer.user,
                        field_changed="expiry_date",
                        old_value="",
                        new_value=str(inv.expiry_date),
                        event_type="field_change",
                        ended_reason=None,
                        snapshot_discount=surplus_discount,
                        snapshot_expiry=surplus_expiry,
                        snapshot_note="Approaching expiry",
                    )

                self.products.append(product)
                self.all_inventory.append(inv)

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.products)} products and {len(self.all_inventory)} inventory batches"))

    # ---------------------------------------------------------
    # Recurring orders
    # ---------------------------------------------------------
    def create_recurring_orders(self):
        self.recurring_orders = []
        self.recurring_items = []

        if not self.customers or not self.products:
            return

        # small subset of customers get recurring orders
        selected_customers = random.sample(self.customers, min(50, len(self.customers)))
        days_choices = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        patterns = ["WK", "FN"]

        for customer in selected_customers:
            addr = customer.user.addresses.filter(is_default_delivery=True).first()
            if not addr:
                continue

            ro = self.RecurringOrder.objects.create(
                user=customer.user,
                delivery_address=addr,
                recurrence_pattern=random.choice(patterns),
                recurrence_day=random.choice(days_choices),
                delivery_day=random.choice(days_choices),
                special_instructions=None,
                status="ACT",
                created_at=timezone.now() - timezone.timedelta(days=random.randint(10, 200)),
            )
            self.recurring_orders.append(ro)

            # 1–3 items per recurring order
            for _ in range(random.randint(1, 3)):
                product = random.choice(self.products)
                roi = self.RecurringOrderItem.objects.create(
                    recurring_order=ro,
                    product=product,
                    quantity=random.randint(1, 5),
                )
                self.recurring_items.append(roi)

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.recurring_orders)} recurring orders and {len(self.recurring_items)} recurring items"))

    # ---------------------------------------------------------
    # Orders with customer + producer patterns + status history
    # ---------------------------------------------------------
    def create_orders_with_patterns(self):
        now = timezone.now()
        self.orders = []
        self.order_items = []
        self.producer_summaries = []

        # Precompute producer "type" based on random assignment
        producer_type = {}
        for producer in self.producers:
            producer_type[producer.id] = random.choice(["veg", "fruit", "dairy", "meat", "eggs", "seasonal"])

        # Map customers to a "loyal producer" if profile is loyal_producer
        loyal_map = {}
        for customer in self.customers:
            profile = self.customer_profiles[customer.id]
            if profile == "loyal_producer":
                loyal_map[customer.id] = random.choice(self.producers)

        for _ in range(NUM_ORDERS):
            customer = random.choice(self.customers)
            profile = self.customer_profiles[customer.id]

            # choose order date with some seasonality + weekly pattern
            days_ago = random.randint(1, 365)
            order_date = now - timezone.timedelta(days=days_ago)

            # weekly shoppers: bias towards more recent + weekends
            if profile == "weekly" and random.random() < 0.6:
                days_ago = random.randint(1, 60)
                order_date = now - timezone.timedelta(days=days_ago)

            # monthly shoppers: spread out
            if profile == "monthly" and random.random() < 0.5:
                days_ago = random.randint(30, 365)
                order_date = now - timezone.timedelta(days=days_ago)

            weekday = order_date.weekday()  # 0=Mon, 6=Sun

            # base number of items
            num_items = random.randint(1, 5)
            if profile == "light":
                num_items = random.randint(1, 2)
            if profile == "category_heavy":
                num_items = random.randint(3, 6)

            delivery_addr = customer.user.addresses.filter(is_default_delivery=True).first()
            billing_addr = customer.user.addresses.filter(is_default_billing=True).first()

            if not delivery_addr:
                continue

            # some orders linked to recurring orders
            recurring_order = None
            if self.recurring_orders and random.random() < 0.2:
                recurring_order = random.choice(self.recurring_orders)
                customer = self.Customer.objects.filter(user=recurring_order.user).first()
                if not customer:
                    recurring_order = None

            order = self.Order.objects.create(
                user=customer.user,
                delivery_address=delivery_addr,
                billing_address=billing_addr,
                recurring_order=recurring_order,
                order_date=order_date,
                total_price=Decimal("0.00"),
                total_discount=Decimal("0.00"),
                total_vat=Decimal("0.00"),
                final_total_price=Decimal("0.00"),
                total_commission=Decimal("0.00"),
                food_miles_total=Decimal("0.00"),
                status=self.Order.Status.PENDING,
            )

            subtotal = Decimal("0.00")
            total_commission = Decimal("0.00")
            total_food_miles = Decimal("0.00")
            producer_totals = {}

            # choose inventory items with producer/category behaviour
            chosen_inventory = []
            for _i in range(num_items):
                inv = random.choice(self.all_inventory)

                # skip zero-stock sometimes
                if inv.remaining_quantity == 0 and random.random() < 0.7:
                    continue

                prod = inv.product
                p_type = producer_type[prod.producer_id]

                month = order_date.month

                # seasonal bias
                if p_type == "fruit" and month in [6, 7, 8, 9] and random.random() < 0.5:
                    fruit_inv = [x for x in self.all_inventory if x.product.category.name == "Fruit"]
                    if fruit_inv:
                        inv = random.choice(fruit_inv)
                        prod = inv.product

                if p_type == "veg" and month in [10, 11, 12, 1, 2] and random.random() < 0.5:
                    veg_inv = [x for x in self.all_inventory if x.product.category.name == "Vegetables"]
                    if veg_inv:
                        inv = random.choice(veg_inv)
                        prod = inv.product

                if p_type == "meat" and weekday in [5, 6] and random.random() < 0.5:
                    meat_inv = [x for x in self.all_inventory if x.product.category.name == "Meat"]
                    if meat_inv:
                        inv = random.choice(meat_inv)
                        prod = inv.product

                # loyal producer bias
                if profile == "loyal_producer" and customer.id in loyal_map and random.random() < 0.7:
                    loyal_producer = loyal_map[customer.id]
                    loyal_inv = [x for x in self.all_inventory if x.product.producer_id == loyal_producer.id]
                    if loyal_inv:
                        inv = random.choice(loyal_inv)
                        prod = inv.product

                chosen_inventory.append(inv)

            if not chosen_inventory:
                order.delete()
                continue

            for inv in chosen_inventory:
                qty = random.randint(1, 10)
                price = inv.product.price
                line_total = price * qty
                commission = (line_total * Decimal("0.05")).quantize(Decimal("0.01"))

                item = self.OrderItem.objects.create(
                    order=order,
                    inventory=inv,
                    product=inv.product,
                    producer=inv.product.producer,
                    quantity=qty,
                    original_unit_price=price,
                    commission_amount=commission,
                    discount_amount=Decimal("0.00"),
                    discount_reason="",
                    vat_amount=Decimal("0.00"),
                    vat_rate=Decimal("0.00"),
                    final_unit_price=price,
                    food_miles=Decimal("1.50"),
                    preparation_deadline=order_date + timezone.timedelta(hours=4),
                )
                self.order_items.append(item)

                # traceability
                self.TraceabilityRecord.objects.create(
                    order_item=item,
                    inventory=inv,
                    product=inv.product,
                    producer=inv.product.producer,
                    customer=customer,
                )

                subtotal += line_total
                total_commission += commission
                total_food_miles += Decimal("1.50")

                pid = inv.product.producer_id
                if pid not in producer_totals:
                    producer_totals[pid] = {
                        "producer": inv.product.producer,
                        "subtotal": Decimal("0.00"),
                    }
                producer_totals[pid]["subtotal"] += line_total

            order.total_price = subtotal.quantize(Decimal("0.01"))
            order.final_total_price = subtotal.quantize(Decimal("0.01"))
            order.total_commission = total_commission.quantize(Decimal("0.01"))
            order.food_miles_total = total_food_miles.quantize(Decimal("0.01"))
            # final status will be COMPLETED after producer summaries progression
            order.save()
            self.orders.append(order)

            # producer summaries + status history + payments + settlements
            for pdata in producer_totals.values():
                producer_subtotal = pdata["subtotal"].quantize(Decimal("0.01"))
                producer_commission = (producer_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
                payout_amount = (producer_subtotal - producer_commission).quantize(Decimal("0.01"))

                summary = self.ProducerOrderSummary.objects.create(
                    order=order,
                    producer=pdata["producer"],
                    subtotal=producer_subtotal,
                    commission_total=producer_commission,
                    vat_total=Decimal("0.00"),
                    payout_amount=payout_amount,
                    delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
                    delivery_date=order_date.date() + timezone.timedelta(days=1),
                    delivery_time_slot="10:00-12:00",
                    address_line1=delivery_addr.line1,
                    address_line2=delivery_addr.line2,
                    city=delivery_addr.city,
                    postcode=delivery_addr.postcode,
                    special_instructions=None,
                    status=self.ProducerOrderSummary.Status.PENDING,
                )
                self.producer_summaries.append(summary)

                # realistic status progression for producer summary
                t0 = order_date
                t1 = t0 + timezone.timedelta(hours=1)
                t2 = t0 + timezone.timedelta(hours=2)
                t3 = t0 + timezone.timedelta(hours=4)
                t4 = t0 + timezone.timedelta(hours=random.randint(6, 10))

                # PENDING -> PREPARING
                self.ProducerOrderStatusHistory.objects.create(
                    producer_order_summary=summary,
                    updated_by=pdata["producer"].user,
                    old_status=self.ProducerOrderSummary.Status.PENDING,
                    new_status=self.ProducerOrderSummary.Status.PREPARING,
                    note="Order is being prepared.",
                    changed_at=t1,
                )
                summary.status = self.ProducerOrderSummary.Status.PREPARING
                summary.save(update_fields=["status"])

                # PREPARING -> PACKAGED
                self.ProducerOrderStatusHistory.objects.create(
                    producer_order_summary=summary,
                    updated_by=pdata["producer"].user,
                    old_status=self.ProducerOrderSummary.Status.PREPARING,
                    new_status=self.ProducerOrderSummary.Status.PACKAGED,
                    note="Order packaged.",
                    changed_at=t2,
                )
                summary.status = self.ProducerOrderSummary.Status.PACKAGED
                summary.save(update_fields=["status"])

                # PACKAGED -> SHIPPED
                self.ProducerOrderStatusHistory.objects.create(
                    producer_order_summary=summary,
                    updated_by=pdata["producer"].user,
                    old_status=self.ProducerOrderSummary.Status.PACKAGED,
                    new_status=self.ProducerOrderSummary.Status.SHIPPED,
                    note="Order shipped.",
                    changed_at=t3,
                )
                summary.status = self.ProducerOrderSummary.Status.SHIPPED
                summary.save(update_fields=["status"])

                # SHIPPED -> COMPLETED
                self.ProducerOrderStatusHistory.objects.create(
                    producer_order_summary=summary,
                    updated_by=pdata["producer"].user,
                    old_status=self.ProducerOrderSummary.Status.SHIPPED,
                    new_status=self.ProducerOrderSummary.Status.COMPLETED,
                    note="Order completed.",
                    changed_at=t4,
                )
                summary.status = self.ProducerOrderSummary.Status.COMPLETED
                summary.save(update_fields=["status"])

                # settlement

                settlement, created = self.ProducerSettlement.objects.get_or_create(
                    producer=pdata["producer"],
                    settlement_week=order_date.date(),
                    defaults={
                        "total_sales": Decimal("0.00"),
                        "total_commission": Decimal("0.00"),
                        "payout_amount": Decimal("0.00"),
                        "payout_status": self.ProducerSettlement.PayoutStatus.PAID,
                        "payment_reference": f"SET-{fake.uuid4()}",
                    }
                )

                # Update running totals
                settlement.total_sales += producer_subtotal
                settlement.total_commission += producer_commission
                settlement.payout_amount += payout_amount
                settlement.save()

                self.SettlementLineItem.objects.create(
                    settlement=settlement,
                    order_item=item,
                    amount=line_total,
                    commission=commission,
                    net_amount=(line_total - commission),
                )

            # payment
            payment = self.Payment.objects.create(
                order=order,
                amount=order.final_total_price,
                payment_method=self.Payment.Method.CARD,
                payment_status=self.Payment.Status.SUCCESS,
                transaction_reference=f"TX-{fake.uuid4()}",
                sandbox_mode=True,
            )

            # final order status
            order.status = self.Order.Status.COMPLETED
            order.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.orders)} orders and {len(self.order_items)} order items"))

    # ---------------------------------------------------------
    # Recalls, notifications, traceability
    # ---------------------------------------------------------
    def create_recalls_and_notifications(self):
        if not self.orders:
            return

        # pick 5 products that have order items
        product_ids_with_orders = list(
            self.OrderItem.objects.values_list("product_id", flat=True).distinct()
        )
        random.shuffle(product_ids_with_orders)
        recalled_product_ids = product_ids_with_orders[:5]

        for pid in recalled_product_ids:
            product = self.Product.objects.get(id=pid)
            # mark removed from sale
            old_status = product.status
            product.status = "RMV"
            product.availability_status = "DIS"
            product.save()

            # inventory history for recall
            invs = self.Inventory.objects.filter(product=product)
            for inv in invs:
                self.InventoryUpdateHistory.objects.create(
                    inventory=inv,
                    user=self.admin.user,
                    field_changed="status",
                    old_value=old_status,
                    new_value="RMV",
                    event_type="field_change",
                    ended_reason=None,
                    snapshot_discount=inv.surplus_discount_percentage,
                    snapshot_expiry=inv.surplus_expiry,
                    snapshot_note="Product recalled and removed from sale",
                )

            severity = random.choice(["LOW", "MED", "HI"])
            notice = self.RecallNotice.objects.create(
                producer=product.producer,
                product=product,
                recall_reason="Potential safety issue identified in seeded data.",
                severity=severity,
                issued_at=timezone.now() - timezone.timedelta(days=random.randint(1, 30)),
                resolved_at=None,
            )

            # find affected order items
            affected_items = self.OrderItem.objects.filter(product=product)
            for item in affected_items:
                order = item.order
                customer = self.Customer.objects.filter(user=order.user).first()
                if not customer:
                    continue

                # recall notification
                self.RecallNotification.objects.create(
                    recall=notice,
                    customer=customer,
                    order=order,
                    notified_by=random.choice(["EML", "APP", "SMS"]),
                    acknowledged=random.random() < 0.5,
                )

                # user notification
                self.Notification.objects.create(
                    user=order.user,
                    product=product,
                    order=order,
                    type="RC",
                    message=f"Recall notice for {product.name}. Please check details.",
                )

        # some generic notifications
        for order in random.sample(self.orders, min(200, len(self.orders))):
            self.Notification.objects.create(
                user=order.user,
                order=order,
                product=None,
                type="OU",
                message=f"Your order #{order.id} has been shipped.",
            )

        self.stdout.write(self.style.SUCCESS(f"[✓] Created recalls for {len(recalled_product_ids)} products and related notifications"))

    # ---------------------------------------------------------
    # Community: recipes, stories, favourites
    # ---------------------------------------------------------
    def create_community_content(self):
        self.recipes = []
        self.farm_stories = []

        RECIPE_TITLES = [
            "Simple Roast Vegetables",
            "Fresh Berry Smoothie",
            "Creamy Cheddar Pasta",
            "Herb‑Roasted Chicken",
            "Farmhouse Vegetable Soup",
            "Classic Apple Crumble",
            "Homemade Yogurt Parfait",
            "Crispy Roast Potatoes",
            "Seasonal Stir‑Fry",
            "Honey‑Glazed Carrots",
        ]

        RECIPE_DESCRIPTIONS = [
            "A quick and wholesome recipe using fresh farm ingredients.",
            "Perfect for busy evenings — simple, healthy, and full of flavour.",
            "A comforting dish made with locally sourced produce.",
            "A family favourite that highlights seasonal ingredients.",
            "Easy to prepare and packed with natural goodness.",
            "A delicious way to enjoy fresh, locally grown produce.",
        ]

        RECIPE_INGREDIENTS = [
            "Carrots", "Potatoes", "Onions", "Garlic", "Milk", "Cheddar Cheese",
            "Strawberries", "Blueberries", "Chicken Breast", "Spinach",
            "Butter", "Olive Oil", "Salt", "Pepper", "Honey", "Eggs"
        ]

        RECIPE_INSTRUCTIONS = [
            "Preheat the oven to 180°C.",
            "Chop all vegetables into even pieces.",
            "Mix ingredients together in a large bowl.",
            "Season generously with salt and pepper.",
            "Cook until golden and tender.",
            "Serve warm and enjoy.",
            "Simmer on low heat for 20 minutes.",
            "Blend until smooth.",
            "Stir occasionally to prevent sticking.",
        ]

        FARM_STORY_TITLES = [
            "A Day on the Farm",
            "Our Sustainable Growing Journey",
            "Meet the Animals",
            "Harvest Season Highlights",
            "Life at the Farm",
            "How We Grow Your Food",
        ]

        FARM_STORY_BODIES = [
            "Our farm has been family‑run for generations, focusing on sustainable and ethical growing practices.",
            "We believe in fresh, local produce grown with care and respect for the environment.",
            "Every season brings new challenges and rewards — and we love sharing that journey with our community.",
            "From planting to harvest, we take pride in producing high‑quality food for local families.",
            "Our team works hard every day to ensure our produce is fresh, flavourful, and responsibly grown.",
            "We are committed to regenerative farming and supporting biodiversity on our land.",
        ]

        seasonal_tags = ["SPR", "SUM", "AUT", "WIN", "ALL"]

        for producer in self.producers:
            # recipes
            num_recipes = random.randint(1, 3)
            for _ in range(num_recipes):
                recipe = self.Recipe.objects.create(
                    producer=producer,
                    moderated_by_admin=self.admin.user,
                    title=random.choice(RECIPE_TITLES),
                    description=random.choice(RECIPE_DESCRIPTIONS),
                    ingredients=random.sample(RECIPE_INGREDIENTS, random.randint(4, 8)),
                    instructions=random.sample(RECIPE_INSTRUCTIONS, random.randint(3, 6)),
                    image="community/img/default_recipe.jpg",
                    seasonal_tag=random.choice(seasonal_tags),
                    status="PUB",
                    moderated_at=timezone.now(),
                )
                self.recipes.append(recipe)

                # link to products
                producer_products = self.Product.objects.filter(producer=producer)
                if producer_products.exists():
                    for prod in random.sample(
                        list(producer_products),
                        min(random.randint(2, 5), producer_products.count()),
                    ):
                        self.RecipeProduct.objects.create(recipe=recipe, product=prod)

            # farm stories
            num_stories = random.randint(1, 2)
            for _ in range(num_stories):
                story = self.FarmStory.objects.create(
                    producer=producer,
                    moderated_by_admin=self.admin.user,
                    title=random.choice(FARM_STORY_TITLES),
                    body=random.choice(FARM_STORY_BODIES),
                    image=None,
                    status="PUB",
                    moderated_at=timezone.now(),
                )
                self.farm_stories.append(story)

        # favourites
        for customer in random.sample(self.customers, min(200, len(self.customers))):
            if not self.recipes:
                break
            fav_recipes = random.sample(self.recipes, min(random.randint(1, 5), len(self.recipes)))
            for recipe in fav_recipes:
                self.FavouriteRecipe.objects.get_or_create(
                    user=customer.user,
                    recipe=recipe,
                )

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.recipes)} recipes, {len(self.farm_stories)} farm stories, and favourites"))

    # ---------------------------------------------------------
    # Reviews
    # ---------------------------------------------------------
    def create_reviews(self):
        self.reviews = []

        REVIEW_TITLES = [
            "Great quality!",
            "Very fresh and tasty",
            "Highly recommended",
            "Good value for money",
            "Exactly what I expected",
            "Will buy again",
            "Fantastic produce",
            "Really impressed",
            "Top quality",
            "Delicious and fresh",
        ]

        REVIEW_BODIES = [
            "Really pleased with the quality. Everything arrived fresh and well‑packed.",
            "Great flavour and very fresh. You can tell it was harvested recently.",
            "Excellent quality and fast delivery. Would definitely order again.",
            "Good value and tastes great. Perfect for weekly meals.",
            "Exceeded my expectations. Fresh, tasty, and sustainably sourced.",
            "Lovely produce. You can tell the farm takes pride in their work.",
            "Arrived in perfect condition. Really impressed with the freshness.",
            "Great taste and very high quality. Highly recommended.",
            "Perfect for cooking and very flavourful. Will be ordering again.",
            "Fresh, delicious, and exactly as described. Very happy with this purchase.",
        ]

        # products that have orders
        product_ids = list(
            self.OrderItem.objects.values_list("product_id", flat=True).distinct()
        )
        random.shuffle(product_ids)
        target_products = product_ids[: min(200, len(product_ids))]

        for pid in target_products:
            product = self.Product.objects.get(id=pid)

            # all order items for this product
            items = list(self.OrderItem.objects.filter(product=product))
            if not items:
                continue

            num_reviews = random.randint(1, 3)
            for _ in range(num_reviews):

                # pick a random order item for this product
                item = random.choice(items)
                order = item.order
                customer = self.Customer.objects.filter(user=order.user).first()
                if not customer:
                    continue

                created_at = timezone.now() - timezone.timedelta(days=random.randint(1, 180))

                review = self.Review.objects.create(
                    product=product,
                    customer=customer,
                    order=order,
                    rating=random.randint(2, 5),
                    title=random.choice(REVIEW_TITLES),
                    text=random.choice(REVIEW_BODIES),
                    anonymous=random.random() < 0.3,
                    status=self.Review.Status.PUBLISHED,
                    moderated_by_admin=None,
                    created_at=created_at,
                )
                self.reviews.append(review)

                # occasional producer response
                if random.random() < 0.4:
                    self.ReviewResponse.objects.create(
                        review=review,
                        producer=product.producer,
                        response_text="Thank you for your feedback!",
                        status=self.ReviewResponse.Status.PUBLISHED,
                        moderated_by_admin=None,
                        created_at=created_at + timezone.timedelta(days=1),
                    )

        self.stdout.write(self.style.SUCCESS(f"[✓] Created {len(self.reviews)} reviews with some producer responses"))

    # ---------------------------------------------------------
    # Admin logs, security logs, distance records
    # ---------------------------------------------------------
    def create_admin_logs(self):
        SECURITY_EVENTS = {
            "LS": "User logged in successfully",
            "LF": "Failed login attempt",
            "PR": "Password reset requested",
            "LO": "User logged out",
            "SA": "Suspicious activity detected",
        }

        ADMIN_POST_TITLES = [
            "Scheduled Maintenance Notice",
            "Platform Update Released",
            "New Producer Guidelines",
            "Community Policy Reminder",
            "Service Improvements Announced",
            "Upcoming Feature Preview",
            "Important Account Security Tips",
            "Seasonal Produce Highlights",
            "Farm Spotlight of the Month",
            "Sustainability Initiatives Update",
        ]

        ADMIN_POST_BODIES = [
            "We are rolling out improvements to enhance platform performance and reliability.",
            "A new update has been deployed with several quality‑of‑life improvements.",
            "Please review the updated producer guidelines to ensure compliance.",
            "We have introduced new measures to improve account security.",
            "Our team is working on new features to improve your experience.",
            "We will be performing scheduled maintenance during off‑peak hours.",
            "Thank you for being part of our community. We appreciate your support.",
            "We are highlighting seasonal produce available this month.",
            "Learn more about our sustainability initiatives and how you can contribute.",
            "We have updated our community policies to ensure a safe environment.",
        ]

        MODERATION_REASONS = [
            "Content flagged for review",
            "Inappropriate language detected",
            "Reported by multiple users",
            "Violation of community guidelines",
            "Incorrect or misleading information",
            "Image quality issues",
            "Spam or promotional content",
            "Duplicate submission",
            "Producer requested removal",
            "Automated moderation check triggered",
        ]

        # Security logs
        all_users = list(self.User.objects.all())
        for user in random.sample(all_users, min(200, len(all_users))):
            event_code = random.choice(list(SECURITY_EVENTS.keys()))
            self.SecurityLog.objects.create(
                user=user,
                event_type=event_code,
                ip_address=fake.ipv4_public(),
                user_agent=fake.user_agent(),
                metadata={"message": SECURITY_EVENTS[event_code]},
            )

        # Admin posts
        categories = ["AN", "UP", "MTN", "POL", "PRO"]
        for _ in range(10):
            self.AdminPost.objects.create(
                admin=self.admin,
                title=random.choice(ADMIN_POST_TITLES),
                body=random.choice(ADMIN_POST_BODIES),
                category=random.choice(categories),
                image=None,
            )

        # Moderation logs
        content_types = ["REC", "FS", "PRO", "RN", "REV", "OTH"]
        actions = ["FLG", "APP", "REJ", "REM", "RES"]
        for _ in range(50):
            producer = random.choice(self.producers)
            self.ModerationLog.objects.create(
                admin=self.admin,
                producer=producer,
                content_type=random.choice(content_types),
                content=random.randint(1, 1000),
                action=random.choice(actions),
                reason=random.choice(MODERATION_REASONS),
            )

        # Distance records (producer ↔ customer)
        for _ in range(200):
            producer = random.choice(self.producers)
            customer = random.choice(self.customers)
            addr = customer.user.addresses.first()
            if not addr:
                continue
            self.DistanceRecord.objects.create(
                producer_postcode=producer.farm_postcode,
                customer_postcode=addr.postcode,
                distance_miles=self.random_money(1, 100),
            )

        self.stdout.write(self.style.SUCCESS("[✓] Created security logs, admin posts, moderation logs, and distance records"))

    # ---------------------------------------------------------
    # Export users to CSV
    # ---------------------------------------------------------
    def export_users_csv(self):
        with open("seeded_users.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["email", "password", "role"])
            writer.writeheader()
            for row in self.seeded_users:
                writer.writerow(row)