# docker compose exec web python manage.py seed_database
# docker compose exec web python manage.py seed_orders
# docker compose exec web python manage.py seed_orders --email mark42@hotmail.com --count 25
# docker compose exec web python manage.py flush

from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Seeds additional targeted product and order-history data for reorder testing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="mark42@hotmail.com",
            help="Email of the existing seeded customer to attach orders to.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=15,
            help="Number of extra pagination orders to create.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.User = apps.get_model("accounts", "User")
        self.Address = apps.get_model("accounts", "Address")
        self.Producer = apps.get_model("accounts", "Producer")

        self.Product = apps.get_model("products", "Product")
        self.Inventory = apps.get_model("products", "Inventory")
        self.Category = apps.get_model("products", "Category")
        self.WholesalePrice = apps.get_model("products", "WholesalePrice")
        try:
            self.ProductType = apps.get_model("products", "ProductType")
        except LookupError:
            self.ProductType = None

        self.Order = apps.get_model("orders", "Order")
        self.OrderItem = apps.get_model("orders", "OrderItem")
        self.ProducerOrderSummary = apps.get_model("orders", "ProducerOrderSummary")
        self.ProducerOrderStatusHistory = apps.get_model(
            "orders", "ProducerOrderStatusHistory"
        )
        self.RecurringOrder = apps.get_model("orders", "RecurringOrder")

        self.customer_email = options["email"]
        self.pagination_count = options["count"]

        if self.pagination_count < 0:
            raise CommandError("--count must be 0 or greater.")

        self.stdout.write(
            self.style.MIGRATE_HEADING("Seeding additional reorder test data...")
        )

        self.load_existing_seed_data()
        self.create_second_customer()
        self.create_reorder_test_catalog()
        self.create_targeted_orders()
        self.create_pagination_orders()

        self.stdout.write(
            self.style.SUCCESS("Additional reorder test data seeded successfully.")
        )

    # ------------------------------------------------------------------
    # Core loading
    # ------------------------------------------------------------------
    def load_existing_seed_data(self):
        try:
            self.customer_user = self.User.objects.get(email=self.customer_email)
        except self.User.DoesNotExist as exc:
            raise CommandError(
                f"Customer with email '{self.customer_email}' was not found. "
                "Run 'python manage.py seed_database' first or provide an existing seeded email."
            ) from exc

        self.customer_address = self.Address.objects.filter(
            user=self.customer_user
        ).first()
        if not self.customer_address:
            raise CommandError(
                f"Address not found for customer '{self.customer_email}'."
            )

        producer_names = {
            "producer": "Blue Cow Farm",
            "producer2": "Cricket Ranch",
            "producer3": "Willow Dairy",
            "producer4": "Brookfield Vegetables",
        }
        loaded = {}
        for attr, farm_name in producer_names.items():
            producer = self.Producer.objects.filter(farm_name=farm_name).first()
            if producer is None:
                raise CommandError(
                    f"Required producer '{farm_name}' was not found. Run 'python manage.py seed_database' first."
                )
            loaded[attr] = producer
            setattr(self, attr, producer)

        required_products = {
            "product1": "Organic Carrots",
            "product2": "Free-range Eggs",
            "product3": "Braeburn Apples",
        }
        for attr, product_name in required_products.items():
            product = self.Product.objects.filter(name=product_name).first()
            if product is None:
                raise CommandError(
                    f"Required product '{product_name}' was not found. Run 'python manage.py seed_database' first."
                )
            setattr(self, attr, product)
            inventory = (
                self.Inventory.objects.filter(product=product).order_by("pk").first()
            )
            if inventory is None:
                raise CommandError(
                    f"Inventory for '{product_name}' was not found. Run 'python manage.py seed_database' first."
                )
            setattr(self, f"inventory{attr[-1]}", inventory)

        self.recurring = self.RecurringOrder.objects.filter(
            user=self.customer_user
        ).first()

        self.stdout.write(
            self.style.SUCCESS("  Existing seed_database records loaded.")
        )

    def create_second_customer(self):
        self.other_user, created = self.User.objects.get_or_create(
            email="othercustomer@example.com",
            defaults={
                "name": "Other Customer",
                "role": self.User.Role_choices.CUSTOMER,
                "phone": "07000000099",
            },
        )

        if created:
            self.other_user.set_password("otherpass123")
            self.other_user.save()

        self.other_address, _ = self.Address.objects.get_or_create(
            user=self.other_user,
            line1="44 Other Street",
            city="Bristol",
            postcode="BS9 1ZZ",
            defaults={
                "line2": "",
                "is_default_delivery": True,
                "is_default_billing": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("  Secondary customer created or reused."))

    # ------------------------------------------------------------------
    # Small utility helpers
    # ------------------------------------------------------------------
    def money(self, value) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"))

    def get_summary_address_from_address(self, address):
        return {
            "summary_address_line1": address.line1,
            "summary_address_line2": address.line2 or "",
            "summary_city": address.city,
            "summary_postcode": address.postcode,
        }

    def get_category(self, name: str):
        category = self.Category.objects.filter(name=name).first()
        if category is None:
            raise CommandError(
                f"Category '{name}' was not found. Run 'python manage.py seed_database' first."
            )
        return category

    def get_or_create_product_type(self, *, category, name: str, description: str = ""):
        if self.ProductType is None:
            return None
        product_type, _ = self.ProductType.objects.get_or_create(
            category=category,
            name=name,
            defaults={"description": description},
        )
        return product_type

    def create_or_update_product(
        self,
        *,
        name,
        producer,
        category,
        price,
        unit,
        farm_origin,
        description="",
        storage_guidance="",
        product_type=None,
        availability_status=None,
        status=None,
        organic_status=None,
        availability_days=30,
        low_stock_threshold=0,
    ):
        today = timezone.localdate()
        now = timezone.now()

        defaults = {
            "producer": producer,
            "category": category,
            "product_type": product_type,
            "moderated_by_admin": None,
            "description": description,
            "price": self.money(price),
            "unit": unit,
            "image": None,
            "low_stock_threshold": low_stock_threshold,
            "farm_origin": farm_origin,
            "organic_certification_status": organic_status
            or self.Product.OrganicStatus.NOT_CERTIFIED,
            "storage_guidance": storage_guidance,
            "availability_start": now,
            "availability_end": now + timezone.timedelta(days=availability_days),
            "availability_status": availability_status
            or self.Product.Availability_status.AVAILABLE,
            "status": status or self.Product.Status.PUBLISHED,
            "moderated_at": now,
        }

        product, created = self.Product.objects.get_or_create(
            name=name, defaults=defaults
        )
        if not created:
            for field, value in defaults.items():
                setattr(product, field, value)
            product.save()
        return product

    def create_or_update_inventory(
        self,
        *,
        product,
        original_quantity,
        remaining_quantity,
        harvest_days_ago,
        expiry_days_from_today,
        expiry_type,
        surplus_status=None,
        surplus_discount_percentage=None,
        surplus_note=None,
        surplus_expiry_days_from_now=None,
    ):
        today = timezone.localdate()
        defaults = {
            "user": getattr(product.producer, "user", None),
            "original_quantity": original_quantity,
            "remaining_quantity": remaining_quantity,
            "harvest_date": today - timezone.timedelta(days=harvest_days_ago),
            "expiry_date": today + timezone.timedelta(days=expiry_days_from_today),
            "expiry_type": expiry_type,
            "surplus_status": surplus_status or self.Inventory.SurplusStatus.NONE,
            "surplus_discount_percentage": surplus_discount_percentage,
            "surplus_note": surplus_note,
            "surplus_expiry": (
                timezone.now() + timezone.timedelta(days=surplus_expiry_days_from_now)
                if surplus_expiry_days_from_now is not None
                else None
            ),
        }

        inventory, created = self.Inventory.objects.get_or_create(
            product=product, defaults=defaults
        )
        if not created:
            for field, value in defaults.items():
                setattr(inventory, field, value)
            inventory.save()
        return inventory

    def ensure_wholesale_tier(self, *, product, min_quantity, unit_price):
        self.WholesalePrice.objects.update_or_create(
            product=product,
            min_quantity=min_quantity,
            defaults={"unit_price": self.money(unit_price)},
        )

    # ------------------------------------------------------------------
    # Product and inventory catalogue for reorder edge cases
    # ------------------------------------------------------------------
    def create_reorder_test_catalog(self):
        fruit = self.get_category("Fruit")
        vegetables = self.get_category("Vegetables")
        eggs = self.get_category("Eggs")

        apple_type = self.get_or_create_product_type(
            category=fruit,
            name="Apple",
            description="Shared type used to seed same-product-type reorder suggestions.",
        )
        carrot_type = self.get_or_create_product_type(
            category=vegetables,
            name="Carrot",
            description="Shared type used to seed carrot suggestion scenarios.",
        )
        egg_type = self.get_or_create_product_type(
            category=eggs,
            name="Egg",
            description="Shared type used for egg suggestion scenarios.",
        )

        # Attach product types to base products so existing products can participate
        # in same-product-type suggestion logic.
        if self.ProductType is not None:
            if self.product1.product_type_id != getattr(carrot_type, "pk", None):
                self.product1.product_type = carrot_type
                self.product1.save(update_fields=["product_type"])
            if self.product2.product_type_id != getattr(egg_type, "pk", None):
                self.product2.product_type = egg_type
                self.product2.save(update_fields=["product_type"])
            if self.product3.product_type_id != getattr(apple_type, "pk", None):
                self.product3.product_type = apple_type
                self.product3.save(update_fields=["product_type"])

        # Refresh key base inventory values that are useful for testing.
        self.inventory1.remaining_quantity = 300
        self.inventory1.original_quantity = 300
        self.inventory1.expiry_date = timezone.localdate() + timezone.timedelta(days=7)
        self.inventory1.expiry_type = self.Inventory.ExpiryType.BEST_BEFORE
        self.inventory1.surplus_status = self.Inventory.SurplusStatus.NONE
        self.inventory1.surplus_discount_percentage = None
        self.inventory1.surplus_expiry = None
        self.inventory1.surplus_note = None
        self.inventory1.save()
        self.ensure_wholesale_tier(
            product=self.product1, min_quantity=100, unit_price=Decimal("0.80")
        )

        self.inventory2.remaining_quantity = 200
        self.inventory2.original_quantity = 200
        self.inventory2.expiry_date = timezone.localdate() + timezone.timedelta(days=14)
        self.inventory2.expiry_type = self.Inventory.ExpiryType.BEST_BEFORE
        self.inventory2.save()

        self.inventory3.remaining_quantity = 250
        self.inventory3.original_quantity = 250
        self.inventory3.expiry_date = timezone.localdate() + timezone.timedelta(days=14)
        self.inventory3.expiry_type = self.Inventory.ExpiryType.BEST_BEFORE
        self.inventory3.surplus_status = self.Inventory.SurplusStatus.SURPLUS_ACTIVE
        self.inventory3.surplus_discount_percentage = Decimal("10.00")
        self.inventory3.surplus_expiry = timezone.now() + timezone.timedelta(days=3)
        self.inventory3.surplus_note = "Seeded surplus sale for reorder testing."
        self.inventory3.save()

        # Same product type, different producer, available alternatives.
        self.product_royal_gala = self.create_or_update_product(
            name="Royal Gala Apples",
            producer=self.producer3,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.40"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer3.farm_name,
            description="Available alternative apple from another producer.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=5,
        )
        self.inventory_royal_gala = self.create_or_update_inventory(
            product=self.product_royal_gala,
            original_quantity=80,
            remaining_quantity=80,
            harvest_days_ago=2,
            expiry_days_from_today=18,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.product_honeycrisp_wholesale = self.create_or_update_product(
            name="Honeycrisp Apples",
            producer=self.producer3,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.90"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer3.farm_name,
            description="Wholesale-enabled apple alternative from another producer.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=10,
        )
        self.inventory_honeycrisp_wholesale = self.create_or_update_inventory(
            product=self.product_honeycrisp_wholesale,
            original_quantity=140,
            remaining_quantity=140,
            harvest_days_ago=1,
            expiry_days_from_today=16,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.ensure_wholesale_tier(
            product=self.product_honeycrisp_wholesale,
            min_quantity=20,
            unit_price=Decimal("2.10"),
        )

        self.product_granny_smith = self.create_or_update_product(
            name="Granny Smith Apples",
            producer=self.producer4,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.60"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer4.farm_name,
            description="Surplus alternative apple from another producer.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.NOT_CERTIFIED,
            low_stock_threshold=5,
        )
        self.inventory_granny_smith = self.create_or_update_inventory(
            product=self.product_granny_smith,
            original_quantity=60,
            remaining_quantity=60,
            harvest_days_ago=1,
            expiry_days_from_today=10,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
            surplus_status=self.Inventory.SurplusStatus.SURPLUS_ACTIVE,
            surplus_discount_percentage=Decimal("20.00"),
            surplus_note="Seeded surplus discount for reorder price-change testing.",
            surplus_expiry_days_from_now=2,
        )
        # Blue Cow Farm - available apple alternatives
        self.product_golden_delicious = self.create_or_update_product(
            name="Golden Delicious Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.35"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Available apple alternative from Blue Cow Farm.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=6,
        )
        self.inventory_golden_delicious = self.create_or_update_inventory(
            product=self.product_golden_delicious,
            original_quantity=75,
            remaining_quantity=75,
            harvest_days_ago=1,
            expiry_days_from_today=14,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_cox_apples = self.create_or_update_product(
            name="Cox Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.45"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Available apple variety from Blue Cow Farm.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.NOT_CERTIFIED,
            low_stock_threshold=5,
        )
        self.inventory_cox_apples = self.create_or_update_inventory(
            product=self.product_cox_apples,
            original_quantity=70,
            remaining_quantity=70,
            harvest_days_ago=2,
            expiry_days_from_today=13,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_red_delicious = self.create_or_update_product(
            name="Red Delicious Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.55"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Another available apple variety from Blue Cow Farm.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=8,
        )
        self.inventory_red_delicious = self.create_or_update_inventory(
            product=self.product_red_delicious,
            original_quantity=90,
            remaining_quantity=90,
            harvest_days_ago=1,
            expiry_days_from_today=15,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.product_bluecow_wholesale_apple = self.create_or_update_product(
            name="Blue Cow Farm Gala Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.80"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Wholesale-enabled apple variety from Blue Cow Farm.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=10,
        )
        self.inventory_bluecow_wholesale_apple = self.create_or_update_inventory(
            product=self.product_bluecow_wholesale_apple,
            original_quantity=120,
            remaining_quantity=120,
            harvest_days_ago=1,
            expiry_days_from_today=16,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.ensure_wholesale_tier(
            product=self.product_bluecow_wholesale_apple,
            min_quantity=20,
            unit_price=Decimal("2.15"),
        )

        # Unavailable products that should still return apple suggestions.
        self.product_hidden_apples = self.create_or_update_product(
            name="Hidden Orchard Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.30"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Historical product now hidden.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.HIDDEN,
        )
        self.inventory_hidden_apples = self.create_or_update_inventory(
            product=self.product_hidden_apples,
            original_quantity=40,
            remaining_quantity=20,
            harvest_days_ago=3,
            expiry_days_from_today=12,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.product_pink_lady = self.create_or_update_product(
            name="Pink Lady Apples",
            producer=self.producer3,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.75"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer3.farm_name,
            description="Available apple variant from the same producer as Royal Gala and Honeycrisp.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=8,
        )
        self.inventory_pink_lady = self.create_or_update_inventory(
            product=self.product_pink_lady,
            original_quantity=90,
            remaining_quantity=90,
            harvest_days_ago=1,
            expiry_days_from_today=14,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_cox_apples = self.create_or_update_product(
            name="Cox Apples",
            producer=self.producer2,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.55"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer2.farm_name,
            description="Available apple variant from the same producer as Braeburn.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.NOT_CERTIFIED,
            low_stock_threshold=6,
        )
        self.inventory_cox_apples = self.create_or_update_inventory(
            product=self.product_cox_apples,
            original_quantity=85,
            remaining_quantity=85,
            harvest_days_ago=2,
            expiry_days_from_today=13,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_fuji_apples = self.create_or_update_product(
            name="Fuji Apples",
            producer=self.producer4,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.65"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer4.farm_name,
            description="Available apple variant from the same producer as Granny Smith.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.NOT_CERTIFIED,
            low_stock_threshold=6,
        )
        self.inventory_fuji_apples = self.create_or_update_inventory(
            product=self.product_fuji_apples,
            original_quantity=70,
            remaining_quantity=70,
            harvest_days_ago=1,
            expiry_days_from_today=12,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_oos_apples = self.create_or_update_product(
            name="Weekend Market Apples",
            producer=self.producer2,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.20"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer2.farm_name,
            description="Historical product now marked unavailable.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.OUT_OF_STOCK,
            status=self.Product.Status.PUBLISHED,
        )
        self.inventory_oos_apples = self.create_or_update_inventory(
            product=self.product_oos_apples,
            original_quantity=40,
            remaining_quantity=15,
            harvest_days_ago=4,
            expiry_days_from_today=8,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_expired_apples = self.create_or_update_product(
            name="Storage Apples",
            producer=self.producer,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.10"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Historical product whose batch is now expired.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
        )
        self.inventory_expired_apples = self.create_or_update_inventory(
            product=self.product_expired_apples,
            original_quantity=35,
            remaining_quantity=12,
            harvest_days_ago=9,
            expiry_days_from_today=-1,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_zero_stock_apples = self.create_or_update_product(
            name="Popular Basket Apples",
            producer=self.producer2,
            category=fruit,
            product_type=apple_type,
            price=Decimal("2.70"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer2.farm_name,
            description="Historical product whose batch now has zero stock.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
        )
        self.inventory_zero_stock_apples = self.create_or_update_inventory(
            product=self.product_zero_stock_apples,
            original_quantity=45,
            remaining_quantity=0,
            harvest_days_ago=2,
            expiry_days_from_today=9,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        # Same category fallback when product_type is null.
        self.product_pear_mix = self.create_or_update_product(
            name="Pear Mix",
            producer=self.producer,
            category=fruit,
            product_type=None,
            price=Decimal("2.15"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Fruit item with no product type to test category fallback suggestions.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
        )
        self.inventory_pear_mix = self.create_or_update_inventory(
            product=self.product_pear_mix,
            original_quantity=50,
            remaining_quantity=18,
            harvest_days_ago=1,
            expiry_days_from_today=11,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        self.product_conference_pears = self.create_or_update_product(
            name="Conference Pears",
            producer=self.producer3,
            category=fruit,
            product_type=None,
            price=Decimal("2.05"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer3.farm_name,
            description="Fruit fallback suggestion from a different producer.",
            storage_guidance="Store in a cool, dry place.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
        )
        self.inventory_conference_pears = self.create_or_update_inventory(
            product=self.product_conference_pears,
            original_quantity=55,
            remaining_quantity=33,
            harvest_days_ago=1,
            expiry_days_from_today=12,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )

        # Wholesale + quantity-adjusted + same-product-type suggestions.
        self.product_heritage_carrots = self.create_or_update_product(
            name="Heritage Carrots",
            producer=self.producer4,
            category=vegetables,
            product_type=carrot_type,
            price=Decimal("2.30"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer4.farm_name,
            description="Alternative carrot product from a different producer.",
            storage_guidance="Keep refrigerated.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.NOT_CERTIFIED,
        )
        self.inventory_heritage_carrots = self.create_or_update_inventory(
            product=self.product_heritage_carrots,
            original_quantity=120,
            remaining_quantity=90,
            harvest_days_ago=2,
            expiry_days_from_today=8,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.ensure_wholesale_tier(
            product=self.product_heritage_carrots,
            min_quantity=80,
            unit_price=Decimal("1.55"),
        )

        # Use a dedicated carrot source product so the live state does not interfere with
        # the base Organic Carrots scenarios.
        self.product_bulk_carrots = self.create_or_update_product(
            name="Bulk Carrots",
            producer=self.producer,
            category=vegetables,
            product_type=carrot_type,
            price=Decimal("2.50"),
            unit=self.Product.Unit.KILOGRAM,
            farm_origin=self.producer.farm_name,
            description="Historical carrot product used for wholesale and quantity-adjusted reorder tests.",
            storage_guidance="Keep refrigerated.",
            availability_status=self.Product.Availability_status.AVAILABLE,
            status=self.Product.Status.PUBLISHED,
            organic_status=self.Product.OrganicStatus.CERTIFIED,
            low_stock_threshold=20,
        )
        self.inventory_bulk_carrots = self.create_or_update_inventory(
            product=self.product_bulk_carrots,
            original_quantity=200,
            remaining_quantity=40,
            harvest_days_ago=2,
            expiry_days_from_today=7,
            expiry_type=self.Inventory.ExpiryType.BEST_BEFORE,
        )
        self.ensure_wholesale_tier(
            product=self.product_bulk_carrots,
            min_quantity=100,
            unit_price=Decimal("0.80"),
        )

        self.reorder_catalog = {
            "available_same_type_source": (
                self.product3,
                self.inventory3,
                self.producer2,
            ),
            "hidden_same_type_source": (
                self.product_hidden_apples,
                self.inventory_hidden_apples,
                self.producer,
            ),
            "availability_unavailable_source": (
                self.product_oos_apples,
                self.inventory_oos_apples,
                self.producer2,
            ),
            "expired_batch_source": (
                self.product_expired_apples,
                self.inventory_expired_apples,
                self.producer,
            ),
            "zero_stock_source": (
                self.product_zero_stock_apples,
                self.inventory_zero_stock_apples,
                self.producer2,
            ),
            "category_fallback_source": (
                self.product_pear_mix,
                self.inventory_pear_mix,
                self.producer,
            ),
            "wholesale_adjusted_source": (
                self.product_bulk_carrots,
                self.inventory_bulk_carrots,
                self.producer,
            ),
            "surplus_source": (
                self.product_granny_smith,
                self.inventory_granny_smith,
                self.producer4,
            ),
        }

        self.stdout.write(
            self.style.SUCCESS(
                "  Reorder catalogue ready: same product type, same category, different producers, "
                "unavailable products, wholesale, surplus, expired stock, and zero-stock cases."
            )
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def create_targeted_orders(self):
        today = timezone.now()
        created_count = 0
        customer_delivery_summary = self.get_summary_address_from_address(
            self.customer_address
        )
        other_delivery_summary = self.get_summary_address_from_address(
            self.other_address
        )

        # Existing general order-history coverage.
        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=8),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            product=self.product1,
            inventory=self.inventory1,
            producer=self.producer,
            quantity=2,
            delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
            summary_status=self.ProducerOrderSummary.Status.SHIPPED,
            delivery_date=(today + timezone.timedelta(days=1)).date(),
            delivery_time_slot="10:00-12:00",
            **customer_delivery_summary,
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=7),
            order_status=self.Order.Status.PENDING,
            recurring_order=None,
            product=self.product2,
            inventory=self.inventory2,
            producer=self.producer,
            quantity=1,
            delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
            summary_status=self.ProducerOrderSummary.Status.PENDING,
            delivery_date=(today + timezone.timedelta(days=2)).date(),
            delivery_time_slot="12:00-14:00",
            **customer_delivery_summary,
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=6),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            product=self.product3,
            inventory=self.inventory3,
            producer=self.producer2,
            quantity=3,
            delivery_or_collection=self.Order.DeliveryOrCollection.COLLECTION,
            summary_status=self.ProducerOrderSummary.Status.PACKAGED,
            delivery_date=(today + timezone.timedelta(days=3)).date(),
            delivery_time_slot="09:00-11:00",
            summary_address_line1="Cricket Ranch Collection Point",
            summary_address_line2="Barn A",
            summary_city="Bristol",
            summary_postcode="BS1 4AK",
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=5),
            order_status=self.Order.Status.CANCELLED,
            recurring_order=None,
            product=self.product3,
            inventory=self.inventory3,
            producer=self.producer2,
            quantity=1,
            delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
            summary_status=self.ProducerOrderSummary.Status.CANCELLED,
            delivery_date=(today + timezone.timedelta(days=2)).date(),
            delivery_time_slot="15:00-17:00",
            **customer_delivery_summary,
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=4),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=self.recurring,
            product=self.product1,
            inventory=self.inventory1,
            producer=self.producer,
            quantity=2,
            delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
            summary_status=self.ProducerOrderSummary.Status.SHIPPED,
            delivery_date=(today + timezone.timedelta(days=4)).date(),
            delivery_time_slot="08:00-10:00",
            **customer_delivery_summary,
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=3),
            order_status=self.Order.Status.READY_FOR_COLLECTION,
            recurring_order=None,
            product=self.product2,
            inventory=self.inventory2,
            producer=self.producer,
            quantity=1,
            delivery_or_collection=self.Order.DeliveryOrCollection.COLLECTION,
            summary_status=self.ProducerOrderSummary.Status.PACKAGED,
            delivery_date=(today + timezone.timedelta(days=1)).date(),
            delivery_time_slot="10:00-12:00",
            summary_address_line1="Blue Cow Farm Collection Point",
            summary_address_line2="Shed 2",
            summary_city="Bristol",
            summary_postcode="BS1 4AB",
        )
        created_count += 1

        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=2, hours=5),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product1,
                    "inventory": self.inventory1,
                    "producer": self.producer,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=2)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 2,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.COLLECTION,
                    "summary_status": self.ProducerOrderSummary.Status.PACKAGED,
                    "delivery_date": (today + timezone.timedelta(days=2)).date(),
                    "delivery_time_slot": "11:00-13:00",
                    "summary_address_line1": "Cricket Ranch Collection Point",
                    "summary_address_line2": "Barn A",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 4AK",
                },
            ],
        )
        created_count += 1

        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=2, hours=1),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product1,
                    "inventory": self.inventory1,
                    "producer": self.producer,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.COLLECTION,
                    "summary_status": self.ProducerOrderSummary.Status.PACKAGED,
                    "delivery_date": (today + timezone.timedelta(days=3)).date(),
                    "delivery_time_slot": "09:00-11:00",
                    "summary_address_line1": "Shared Pickup Hub",
                    "summary_address_line2": "Bay 1",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 9AA",
                },
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.COLLECTION,
                    "summary_status": self.ProducerOrderSummary.Status.PACKAGED,
                    "delivery_date": (today + timezone.timedelta(days=3)).date(),
                    "delivery_time_slot": "09:00-11:00",
                    "summary_address_line1": "Shared Pickup Hub",
                    "summary_address_line2": "Bay 1",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 9AA",
                },
            ],
        )
        created_count += 1

        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=1, hours=20),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product1,
                    "inventory": self.inventory1,
                    "producer": self.producer,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.COLLECTION,
                    "summary_status": self.ProducerOrderSummary.Status.PACKAGED,
                    "delivery_date": (today + timezone.timedelta(days=3)).date(),
                    "delivery_time_slot": "09:00-11:00",
                    "summary_address_line1": "Blue Cow Farm Collection Point",
                    "summary_address_line2": "Shed 2",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 4AB",
                },
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.COLLECTION,
                    "summary_status": self.ProducerOrderSummary.Status.PACKAGED,
                    "delivery_date": (today + timezone.timedelta(days=3)).date(),
                    "delivery_time_slot": "09:00-11:00",
                    "summary_address_line1": "Cricket Ranch Collection Point",
                    "summary_address_line2": "Barn A",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 4AK",
                },
            ],
        )
        created_count += 1

        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=1, hours=10),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product1,
                    "inventory": self.inventory1,
                    "producer": self.producer,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=5)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=5)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
            ],
        )
        created_count += 1

        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=1, hours=3),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product1,
                    "inventory": self.inventory1,
                    "producer": self.producer,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=6)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 1,
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=7)).date(),
                    "delivery_time_slot": "12:00-14:00",
                    **customer_delivery_summary,
                },
            ],
        )
        created_count += 1

        self.create_single_producer_order(
            user=self.other_user,
            address=self.other_address,
            order_date=today - timezone.timedelta(days=1),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            product=self.product1,
            inventory=self.inventory1,
            producer=self.producer,
            quantity=1,
            delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
            summary_status=self.ProducerOrderSummary.Status.SHIPPED,
            delivery_date=(today + timezone.timedelta(days=1)).date(),
            delivery_time_slot="10:00-12:00",
            **other_delivery_summary,
        )
        created_count += 1

        # Reorder-specific edge cases for Mark.
        edge_case_specs = [
            {
                "days_ago": 16,
                "product": self.product3,
                "inventory": self.inventory3,
                "producer": self.producer2,
                "quantity": 4,
                "item_original_unit_price": Decimal("2.50"),
                "item_final_unit_price": Decimal("2.50"),
                "label": "available source with same product type suggestions",
            },
            {
                "days_ago": 15,
                "product": self.product_hidden_apples,
                "inventory": self.inventory_hidden_apples,
                "producer": self.producer,
                "quantity": 2,
                "item_original_unit_price": Decimal("2.30"),
                "item_final_unit_price": Decimal("2.30"),
                "label": "hidden product with same product type suggestions",
            },
            {
                "days_ago": 14,
                "product": self.product_oos_apples,
                "inventory": self.inventory_oos_apples,
                "producer": self.producer2,
                "quantity": 2,
                "item_original_unit_price": Decimal("2.20"),
                "item_final_unit_price": Decimal("2.20"),
                "label": "availability unavailable product with suggestions",
            },
            {
                "days_ago": 13,
                "product": self.product_expired_apples,
                "inventory": self.inventory_expired_apples,
                "producer": self.producer,
                "quantity": 2,
                "item_original_unit_price": Decimal("2.10"),
                "item_final_unit_price": Decimal("2.10"),
                "label": "expired batch with suggestions",
            },
            {
                "days_ago": 12,
                "product": self.product_zero_stock_apples,
                "inventory": self.inventory_zero_stock_apples,
                "producer": self.producer2,
                "quantity": 2,
                "item_original_unit_price": Decimal("2.70"),
                "item_final_unit_price": Decimal("2.70"),
                "label": "zero-stock batch with suggestions",
            },
            {
                "days_ago": 11,
                "product": self.product_pear_mix,
                "inventory": self.inventory_pear_mix,
                "producer": self.producer,
                "quantity": 3,
                "item_original_unit_price": Decimal("2.15"),
                "item_final_unit_price": Decimal("2.15"),
                "label": "category fallback suggestions when product type is null",
            },
            {
                "days_ago": 10,
                "product": self.product_bulk_carrots,
                "inventory": self.inventory_bulk_carrots,
                "producer": self.producer,
                "quantity": 120,
                "item_original_unit_price": Decimal("0.80"),
                "item_final_unit_price": Decimal("0.80"),
                "label": "wholesale price change and quantity adjusted reorder",
            },
            {
                "days_ago": 9,
                "product": self.product_granny_smith,
                "inventory": self.inventory_granny_smith,
                "producer": self.producer4,
                "quantity": 5,
                "item_original_unit_price": Decimal("2.60"),
                "item_final_unit_price": Decimal("2.60"),
                "label": "surplus price change reorder",
            },
        ]

        for spec in edge_case_specs:
            self.create_single_producer_order(
                user=self.customer_user,
                address=self.customer_address,
                order_date=today - timezone.timedelta(days=spec["days_ago"]),
                order_status=self.Order.Status.COMPLETED,
                recurring_order=None,
                product=spec["product"],
                inventory=spec["inventory"],
                producer=spec["producer"],
                quantity=spec["quantity"],
                delivery_or_collection=self.Order.DeliveryOrCollection.DELIVERY,
                summary_status=self.ProducerOrderSummary.Status.SHIPPED,
                delivery_date=(today + timezone.timedelta(days=2)).date(),
                delivery_time_slot="10:00-12:00",
                item_original_unit_price=spec["item_original_unit_price"],
                item_final_unit_price=spec["item_final_unit_price"],
                summary_note=f"Seeded reorder edge case: {spec['label']}.",
                **customer_delivery_summary,
            )
            created_count += 1

        # Multi-producer reorder preview case mixing available and unavailable items.
        self.create_multi_producer_order(
            user=self.customer_user,
            address=self.customer_address,
            order_date=today - timezone.timedelta(days=17),
            order_status=self.Order.Status.COMPLETED,
            recurring_order=None,
            items=[
                {
                    "product": self.product3,
                    "inventory": self.inventory3,
                    "producer": self.producer2,
                    "quantity": 2,
                    "item_original_unit_price": Decimal("2.50"),
                    "item_final_unit_price": Decimal("2.50"),
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=2)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
                {
                    "product": self.product_hidden_apples,
                    "inventory": self.inventory_hidden_apples,
                    "producer": self.producer,
                    "quantity": 2,
                    "item_original_unit_price": Decimal("2.30"),
                    "item_final_unit_price": Decimal("2.30"),
                    "delivery_or_collection": self.Order.DeliveryOrCollection.DELIVERY,
                    "summary_status": self.ProducerOrderSummary.Status.SHIPPED,
                    "delivery_date": (today + timezone.timedelta(days=2)).date(),
                    "delivery_time_slot": "10:00-12:00",
                    **customer_delivery_summary,
                },
            ],
            summary_note="Seeded multi-producer reorder mix for preview testing.",
        )
        created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"  Targeted orders created: {created_count}")
        )

    def create_pagination_orders(self):
        base_time = timezone.now() - timezone.timedelta(days=20)
        created_count = 0
        customer_delivery_summary = self.get_summary_address_from_address(
            self.customer_address
        )

        products = [
            self.product1,
            self.product2,
            self.product3,
            self.product_royal_gala,
        ]
        inventories = [
            self.inventory1,
            self.inventory2,
            self.inventory3,
            self.inventory_royal_gala,
        ]
        producers = [self.producer, self.producer, self.producer2, self.producer3]

        for i in range(self.pagination_count):
            product = products[i % len(products)]
            inventory = inventories[i % len(inventories)]
            producer = producers[i % len(producers)]

            order_status = (
                self.Order.Status.COMPLETED if i % 2 == 0 else self.Order.Status.PENDING
            )
            delivery_type = (
                self.Order.DeliveryOrCollection.DELIVERY
                if i % 2 == 0
                else self.Order.DeliveryOrCollection.COLLECTION
            )
            summary_status = (
                self.ProducerOrderSummary.Status.SHIPPED
                if delivery_type == self.Order.DeliveryOrCollection.DELIVERY
                else self.ProducerOrderSummary.Status.PACKAGED
            )
            recurring_order = self.recurring if i % 4 == 0 else None
            summary_address = (
                customer_delivery_summary
                if delivery_type == self.Order.DeliveryOrCollection.DELIVERY
                else {
                    "summary_address_line1": "Shared Pickup Hub",
                    "summary_address_line2": "Bay 1",
                    "summary_city": "Bristol",
                    "summary_postcode": "BS1 9AA",
                }
            )

            self.create_single_producer_order(
                user=self.customer_user,
                address=self.customer_address,
                order_date=base_time + timezone.timedelta(days=i),
                order_status=order_status,
                recurring_order=recurring_order,
                product=product,
                inventory=inventory,
                producer=producer,
                quantity=(i % 4) + 1,
                delivery_or_collection=delivery_type,
                summary_status=summary_status,
                delivery_date=(base_time + timezone.timedelta(days=i + 2)).date(),
                delivery_time_slot="10:00-12:00",
                **summary_address,
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"  Pagination orders created: {created_count}")
        )

    # ------------------------------------------------------------------
    # Order helpers
    # ------------------------------------------------------------------
    def create_single_producer_order(
        self,
        *,
        user,
        address,
        order_date,
        order_status,
        recurring_order,
        product,
        inventory,
        producer,
        quantity,
        delivery_or_collection,
        summary_status,
        delivery_date,
        delivery_time_slot,
        summary_address_line1,
        summary_address_line2,
        summary_city,
        summary_postcode,
        item_original_unit_price=None,
        item_final_unit_price=None,
        item_discount_amount=Decimal("0.00"),
        item_discount_reason="",
        item_vat_amount=Decimal("0.00"),
        item_vat_rate=Decimal("0.00"),
        item_food_miles=Decimal("1.50"),
        summary_note="Seeded order history test data",
    ):
        quantity_decimal = Decimal(str(quantity))
        unit_price = self.money(
            item_original_unit_price
            if item_original_unit_price is not None
            else product.price
        )
        final_unit_price = self.money(
            item_final_unit_price if item_final_unit_price is not None else unit_price
        )
        subtotal = self.money(final_unit_price * quantity_decimal)
        commission_total = self.money(subtotal * Decimal("0.05"))
        vat_total = self.money(item_vat_amount)
        final_total = subtotal
        food_miles_total = self.money(item_food_miles * quantity_decimal)

        order = self.Order.objects.create(
            user=user,
            delivery_address=address,
            billing_address=address,
            recurring_order=recurring_order,
            order_date=order_date,
            total_price=subtotal,
            total_discount=self.money(item_discount_amount),
            total_vat=vat_total,
            final_total_price=final_total,
            total_commission=commission_total,
            food_miles_total=food_miles_total,
            status=order_status,
        )

        item_commission = self.money(final_unit_price * Decimal("0.05"))

        self.OrderItem.objects.create(
            order=order,
            inventory=inventory,
            product=product,
            producer=producer,
            quantity=quantity,
            original_unit_price=unit_price,
            commission_amount=item_commission,
            discount_amount=self.money(item_discount_amount),
            discount_reason=item_discount_reason,
            vat_amount=vat_total,
            vat_rate=self.money(item_vat_rate),
            final_unit_price=final_unit_price,
            food_miles=self.money(item_food_miles),
            preparation_deadline=order_date + timezone.timedelta(hours=4),
        )

        summary = self.ProducerOrderSummary.objects.create(
            order=order,
            producer=producer,
            subtotal=subtotal,
            commission_total=commission_total,
            vat_total=vat_total,
            payout_amount=self.money(subtotal - commission_total),
            delivery_date=delivery_date,
            delivery_or_collection=delivery_or_collection,
            delivery_time_slot=delivery_time_slot,
            address_line1=summary_address_line1,
            address_line2=summary_address_line2,
            city=summary_city,
            postcode=summary_postcode,
            special_instructions=summary_note,
            status=summary_status,
        )

        self.ProducerOrderStatusHistory.objects.create(
            producer_order_summary=summary,
            updated_by=producer.user,
            old_status=self.ProducerOrderSummary.Status.PENDING,
            new_status=summary_status,
            note="Seeded status history entry.",
            changed_at=order_date,
        )
        return order

    def create_multi_producer_order(
        self,
        *,
        user,
        address,
        order_date,
        order_status,
        recurring_order,
        items,
        summary_note="Seeded multi-producer order history test data",
    ):
        order = self.Order.objects.create(
            user=user,
            delivery_address=address,
            billing_address=address,
            recurring_order=recurring_order,
            order_date=order_date,
            total_price=Decimal("0.00"),
            total_discount=Decimal("0.00"),
            total_vat=Decimal("0.00"),
            final_total_price=Decimal("0.00"),
            total_commission=Decimal("0.00"),
            food_miles_total=Decimal("0.00"),
            status=order_status,
        )

        total_price = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_vat = Decimal("0.00")
        total_commission = Decimal("0.00")
        total_food_miles = Decimal("0.00")
        summary_data = {}

        for item in items:
            product = item["product"]
            inventory = item["inventory"]
            producer = item["producer"]
            quantity = item["quantity"]
            quantity_decimal = Decimal(str(quantity))

            original_unit_price = self.money(
                item.get("item_original_unit_price", product.price)
            )
            final_unit_price = self.money(
                item.get("item_final_unit_price", original_unit_price)
            )
            discount_amount = self.money(
                item.get("item_discount_amount", Decimal("0.00"))
            )
            vat_amount = self.money(item.get("item_vat_amount", Decimal("0.00")))
            vat_rate = self.money(item.get("item_vat_rate", Decimal("0.00")))
            food_miles = self.money(item.get("item_food_miles", Decimal("1.50")))

            line_subtotal = self.money(final_unit_price * quantity_decimal)
            line_commission = self.money(line_subtotal * Decimal("0.05"))
            line_food_miles = self.money(food_miles * quantity_decimal)

            self.OrderItem.objects.create(
                order=order,
                inventory=inventory,
                product=product,
                producer=producer,
                quantity=quantity,
                original_unit_price=original_unit_price,
                commission_amount=self.money(final_unit_price * Decimal("0.05")),
                discount_amount=discount_amount,
                discount_reason=item.get("item_discount_reason", ""),
                vat_amount=vat_amount,
                vat_rate=vat_rate,
                final_unit_price=final_unit_price,
                food_miles=food_miles,
                preparation_deadline=order_date + timezone.timedelta(hours=4),
            )

            total_price += line_subtotal
            total_discount += discount_amount
            total_vat += vat_amount
            total_commission += line_commission
            total_food_miles += line_food_miles

            producer_key = producer.pk
            data = summary_data.get(producer_key)
            if data is None:
                data = {
                    "producer": producer,
                    "subtotal": Decimal("0.00"),
                    "commission_total": Decimal("0.00"),
                    "vat_total": Decimal("0.00"),
                    "payout_amount": Decimal("0.00"),
                    "delivery_date": item["delivery_date"],
                    "delivery_or_collection": item["delivery_or_collection"],
                    "delivery_time_slot": item["delivery_time_slot"],
                    "address_line1": item["summary_address_line1"],
                    "address_line2": item["summary_address_line2"],
                    "city": item["summary_city"],
                    "postcode": item["summary_postcode"],
                    "status": item["summary_status"],
                }
                summary_data[producer_key] = data

            data["subtotal"] += line_subtotal
            data["commission_total"] += line_commission
            data["vat_total"] += vat_amount
            data["payout_amount"] += line_subtotal - line_commission

        order.total_price = self.money(total_price)
        order.total_discount = self.money(total_discount)
        order.total_vat = self.money(total_vat)
        order.final_total_price = self.money(total_price)
        order.total_commission = self.money(total_commission)
        order.food_miles_total = self.money(total_food_miles)
        order.save()

        for data in summary_data.values():
            summary = self.ProducerOrderSummary.objects.create(
                order=order,
                producer=data["producer"],
                subtotal=self.money(data["subtotal"]),
                commission_total=self.money(data["commission_total"]),
                vat_total=self.money(data["vat_total"]),
                payout_amount=self.money(data["payout_amount"]),
                delivery_date=data["delivery_date"],
                delivery_or_collection=data["delivery_or_collection"],
                delivery_time_slot=data["delivery_time_slot"],
                address_line1=data["address_line1"],
                address_line2=data["address_line2"],
                city=data["city"],
                postcode=data["postcode"],
                special_instructions=summary_note,
                status=data["status"],
            )

            self.ProducerOrderStatusHistory.objects.create(
                producer_order_summary=summary,
                updated_by=data["producer"].user,
                old_status=self.ProducerOrderSummary.Status.PENDING,
                new_status=data["status"],
                note="Seeded multi-producer status history entry.",
                changed_at=order_date,
            )

        return order
