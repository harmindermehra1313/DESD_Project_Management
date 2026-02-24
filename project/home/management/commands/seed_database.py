# Run this to seed the database with a few entries:
# docker compose exec web python manage.py seed_database

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps

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

        self.stdout.write(self.style.SUCCESS("  Users: customer & admin created."))

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
    def create_producers(self):
        self.producer = self.Producer.objects.create(
            user=self.admin_user,
            farm_name="Blue Cow Farm",
            farm_description="A small family-run organic farm.",
            farm_postcode="BS1 4AB",
            contact_email="contact@bluecowfarm.com",
            contact_phone="07123456789",
            approved_by_admin=self.admin_user,
            is_approved=True,
            approved_at=timezone.now(),
            payout_method="BANK_TRANSFER",
            bank_account_name="Blue Cow Farm Ltd",
            bank_account_number="12345678",
            bank_sort_code="12-34-56",
            paypal_email=None,
            payout_notes="Initial setup for testing.",
            organic_certification_number="ORG-12345",
        )

        self.stdout.write(self.style.SUCCESS("  Producer created."))

    # Categories
    def create_categories(self):
        self.category = self.Category.objects.create(
            name="Vegetables",
            description="Fresh produce",
            vat="0.0"
        )
        self.stdout.write(self.style.SUCCESS("  Category created."))

    # Allergens
    def create_allergens(self):
        allergen_names = ["Eggs", "Milk", "Nuts", "Soya", "Sesame"]
        self.allergens = [
            self.Allergen.objects.get_or_create(name=name)[0]
            for name in allergen_names
        ]
        self.stdout.write(self.style.SUCCESS("  Allergens created."))

    # Products
    def create_products(self):
        today = timezone.now().date()
        now = timezone.now()

        # Product 1 - Organic Carrots
        self.product1 = self.Product.objects.create(
            producer=self.producer,
            category=self.category,
            moderated_by_admin=None, # optional

            name="Organic Carrots",
            description="Fresh organic carrots.",
            price=2.50,
            unit="KG",
            image="carrots.jpg",

            stock_quantity=100,
            low_stock_threshold=10,

            harvest_date=today,
            farm_origin="Blue Cow Farm",
            organic_certification_status="CERTIFIED",
            storage_guidance="Keep refrigerated.",

            expiry_date=today + timezone.timedelta(days=7),
            expiry_type="BEST BEFORE",

            availability_start=today,
            availability_end=today + timezone.timedelta(days=30),
            availability_status="AVAILABLE",

            surplus_status="NONE",
            surplus_discount_percentage=0.00,
            surplus_expiry=None,
            surplus_note=None,

            created_at=now,
            updated_at=now,
            status="PUBLISHED",
            moderated_at=None,
        )

        # Product 2 - Free-range Eggs
        self.product2 = self.Product.objects.create(
            producer=self.producer,
            category=self.category,
            moderated_by_admin=None,

            name="Free-range Eggs",
            description="A dozen free-range eggs.",
            price=3.00,
            unit="EACH",
            image="eggs.jpg",

            stock_quantity=50,
            low_stock_threshold=5,

            harvest_date=today,
            farm_origin="Blue Cow Farm",
            organic_certification_status="NOT_CERTIFIED",
            storage_guidance="Store in a cool, dry place.",

            expiry_date=today + timezone.timedelta(days=14),
            expiry_type="USE BY",

            availability_start=today,
            availability_end=today + timezone.timedelta(days=60),
            availability_status="AVAILABLE",

            surplus_status="NONE",
            surplus_discount_percentage=0.00,
            surplus_expiry=None,
            surplus_note=None,

            created_at=now,
            updated_at=now,
            status="PUBLISHED",
            moderated_at=None,
        )

        self.ProductAllergen.objects.create(
            product=self.product2,
            allergen=self.allergens[0] # Eggs
        )

        self.ProductUpdateHistory.objects.create(
            product=self.product1,
            user=self.customer_user,
            field_changed="price",
            old_value="2.00",
            new_value="2.50",
            changed_at=timezone.now(),
        )

        self.WholesalePrice.objects.create(
            product=self.product1,
            min_quantity=100,
            unit_price=1.80
        )

        self.stdout.write(self.style.SUCCESS("  Products + related tables created."))

    # Orders
    def create_orders(self):
        now = timezone.now()
        today = now.date()

        # Create Order
        self.order = self.Order.objects.create(
            user=self.customer_user,
            delivery_address = self.customer_address,
            recurring_order=None, # optional

            order_date=now,
            delivery_or_collection="DELIVERY",
            delivery_date=now + timezone.timedelta(days=1),

            total_price=5.50,
            total_discount=0.00,
            final_total_price=5.50,
            total_commission=round(5.50 * 0.05, 2), # 5% commission
            food_miles_total=3.0, # example miles

            status="COMPLETED",
        )

        # Order Item 1 – Carrots
        original_price_1 = 2.50
        commission_1 = round(original_price_1 * 0.05, 2)

        self.order_item1 = self.OrderItem.objects.create(
            order=self.order,
            product=self.product1,
            producer=self.producer,

            quantity=1,
            original_unit_price=2.50,
            commission_amount=commission_1,
            discount_amount=0.00,
            discount_reason="",
            final_unit_price=original_price_1,
            food_miles=1.5,
            preparation_deadline=now + timezone.timedelta(hours=4),
        )

        # Add traceability
        self.TraceabilityRecord.objects.create(
            order_item=self.order_item1,
            product=self.product1,
            producer=self.producer,
            customer=self.customer,
            timestamp=now,
        )

        self.stdout.write(self.style.SUCCESS("  Order 1 traceability record created."))


        # Order Item 2 - Eggs
        original_price_2 = 3.00
        commission_2 = round(original_price_2 * 0.05, 2)

        self.order_item2 = self.OrderItem.objects.create(
            order=self.order,
            product=self.product2,
            producer=self.producer,

            quantity=1,
            original_unit_price=3.00,
            commission_amount=commission_2,
            discount_amount=0.00,
            discount_reason="",
            final_unit_price=original_price_2,
            food_miles=1.5,
            preparation_deadline=now + timezone.timedelta(hours=4),
        )

        # Traceability for item 2
        self.TraceabilityRecord.objects.create(
            order_item=self.order_item2,
            product=self.product2,
            producer=self.producer,
            customer=self.customer,
            timestamp=now,
        )

        # Producer summary
        self.order_summary = self.ProducerOrderSummary.objects.create(
            order=self.order,
            producer=self.producer,

            subtotal=5.50,
            commission_total=round(5.50 * 0.05, 2),
            payout_amount=5.50 - round(5.50 * 0.05, 2),

            delivery_date=timezone.now() + timezone.timedelta(days=1),

            special_instructions=None,
            status=self.ProducerOrderSummary.Status.SHIPPED,
        )

        # Status history
        self.ProducerOrderStatusHistory.objects.create(
            producer_order_summary=self.order_summary,
            updated_by=self.admin_user,

            old_status=self.ProducerOrderSummary.Status.PENDING,
            new_status=self.ProducerOrderSummary.Status.SHIPPED,

            note="Order completed successfully.",
            changed_at=now,
        )

        self.stdout.write(self.style.SUCCESS("  Order + items + summaries + traceability created."))

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
            status="PUBLISHED",
            created_at=timezone.now(),
        )

        self.ReviewResponse.objects.create(
            review=self.review,
            producer=self.producer,
            response_text="Thank you for your feedback!",
            status="PUBLISHED",
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
            status="PUBLISHED",
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
            status="PUBLISHED",
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
    def create_payments_and_settlements(self):
        self.Payment.objects.create(
            order=self.order,
            amount=5.50,
            payment_method="CARD",
            payment_status="SUCCESS",
            transaction_reference="TEST-TXN-12345",
            sandbox_mode=True,
        )

        settlement = self.ProducerSettlement.objects.create(
            producer=self.producer,
            settlement_week=timezone.now().date(),
            total_sales=5.50,
            total_commission=round(5.50 * 0.05, 2),
            payment_reference="SETTLE-001",
            payout_amount=5.50 - round(5.50 * 0.05, 2),
            payout_status="PAID",
            generated_at=timezone.now(),
        )

        self.SettlementLineItem.objects.create(
            settlement=settlement,
            order_item=self.order_item1,
            amount=2.50,
            commission=round(2.50 * 0.05, 2),
            net_amount=2.50 - round(2.50 * 0.05, 2),
        )

        self.SettlementLineItem.objects.create(
            settlement=settlement,
            order_item=self.order_item2,
            amount=3.00,
            commission=round(3.00 * 0.05, 2),
            net_amount=3.00 - round(3.00 * 0.05, 2),
        )

        self.stdout.write(self.style.SUCCESS("  Payments + settlements created."))
