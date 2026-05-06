# docker compose exec web python manage.py populate_products --count 250 --clear
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Producer
from products.models import Category, Inventory, Product, WholesalePrice
from products.services.product_type_inference import get_or_create_inferred_product_type


CATEGORY_SEEDS = [
    {
        "name": "Fruit",
        "food_groups": Category.FoodGroups.FRUIT,
        "description": "Fresh local and seasonal fruit.",
        "vat": Decimal("0.00"),
    },
    {
        "name": "Vegetables",
        "food_groups": Category.FoodGroups.VEGETABLES,
        "description": "Fresh local vegetables and salad produce.",
        "vat": Decimal("0.00"),
    },
    {
        "name": "Meat",
        "food_groups": Category.FoodGroups.MEAT,
        "description": "Fresh meat products from local producers.",
        "vat": Decimal("0.00"),
    },
    {
        "name": "Dairy and Eggs",
        "food_groups": Category.FoodGroups.DAIRY,
        "description": "Milk, cheese, butter, yoghurt and eggs.",
        "vat": Decimal("0.00"),
    },
    {
        "name": "Seasonal",
        "food_groups": Category.FoodGroups.PICKLED,
        "description": "Seasonal produce boxes and mixed packs.",
        "vat": Decimal("0.00"),
    },
]


PRODUCT_SEEDS = [
    # Fruit
    ("Fruit", "Royal Gala Apples", "Crisp, sweet apples suitable for snacking and lunch boxes.", "KG", "2.40"),
    ("Fruit", "Braeburn Apples", "Firm apples with a balanced sweet and sharp flavour.", "KG", "2.30"),
    ("Fruit", "Conference Pears", "Juicy pears harvested at peak freshness.", "KG", "2.60"),
    ("Fruit", "Strawberries", "Sweet seasonal strawberries grown locally.", "PK", "3.20"),
    ("Fruit", "Raspberries", "Soft raspberries ideal for desserts and breakfast bowls.", "PK", "3.50"),
    ("Fruit", "Blueberries", "Fresh blueberries packed in small punnets.", "PK", "3.10"),
    ("Fruit", "Victoria Plums", "Sweet plums with a rich seasonal flavour.", "KG", "2.80"),
    ("Fruit", "Morello Cherries", "Tart cherries suitable for baking and preserves.", "PK", "3.80"),

    # Vegetables
    ("Vegetables", "Maris Piper Potatoes", "Versatile potatoes suitable for roasting, mashing and chips.", "KG", "1.70"),
    ("Vegetables", "Chantenay Carrots", "Small sweet carrots with a crisp texture.", "KG", "1.60"),
    ("Vegetables", "Red Onions", "Sharp red onions suitable for salads and cooking.", "KG", "1.40"),
    ("Vegetables", "Spring Onions", "Fresh spring onions for salads, stir-fries and garnishes.", "BN", "1.10"),
    ("Vegetables", "Curly Kale", "Nutritious leafy greens suitable for steaming or stir-frying.", "BN", "1.80"),
    ("Vegetables", "Baby Spinach", "Tender spinach leaves suitable for salads and cooking.", "PK", "2.00"),
    ("Vegetables", "Tenderstem Broccoli", "Tender broccoli stems with a mild flavour.", "BN", "2.30"),
    ("Vegetables", "Cherry Tomatoes", "Sweet cherry tomatoes suitable for salads and sauces.", "PK", "2.40"),
    ("Vegetables", "Chestnut Mushrooms", "Earthy mushrooms suitable for frying, roasting and sauces.", "PK", "2.20"),
    ("Vegetables", "Butternut Squash", "Sweet squash suitable for roasting and soups.", "EA", "2.50"),

    # Meat
    ("Meat", "Chicken Breasts", "Fresh chicken breasts suitable for roasting, grilling and meal prep.", "KG", "7.50"),
    ("Meat", "Chicken Thighs", "Juicy chicken thighs suitable for roasting and curries.", "KG", "5.80"),
    ("Meat", "Pork Sausages", "Traditional pork sausages made in small batches.", "PK", "4.20"),
    ("Meat", "Beef Mince", "Fresh beef mince suitable for sauces, pies and burgers.", "KG", "6.80"),
    ("Meat", "Lamb Chops", "Tender lamb chops from local producers.", "KG", "9.50"),
    ("Meat", "Pork Belly", "Rich pork belly suitable for roasting.", "KG", "7.20"),
    ("Meat", "Turkey Breast", "Lean turkey breast suitable for roasting or slicing.", "KG", "8.00"),

    # Dairy and Eggs
    ("Dairy and Eggs", "Whole Milk", "Fresh whole milk from local dairy producers.", "L", "1.50"),
    ("Dairy and Eggs", "Semi-Skimmed Milk", "Fresh semi-skimmed milk for everyday use.", "L", "1.40"),
    ("Dairy and Eggs", "Free Range Eggs", "Free range eggs from local farms.", "BX", "2.80"),
    ("Dairy and Eggs", "Mature Cheddar", "Full-flavoured mature cheddar cheese.", "KG", "8.50"),
    ("Dairy and Eggs", "Goat Cheese", "Soft goat cheese with a creamy texture.", "PK", "3.70"),
    ("Dairy and Eggs", "Natural Yoghurt", "Plain natural yoghurt suitable for breakfast and cooking.", "EA", "2.10"),
    ("Dairy and Eggs", "Salted Butter", "Traditional salted butter.", "EA", "2.40"),
    ("Dairy and Eggs", "Double Cream", "Rich double cream suitable for desserts and cooking.", "ML", "1.90"),

    # Seasonal
    ("Seasonal", "Seasonal Vegetable Box", "A mixed box of fresh seasonal vegetables.", "BX", "12.00"),
    ("Seasonal", "Seasonal Fruit Box", "A mixed box of fresh seasonal fruit.", "BX", "13.00"),
    ("Seasonal", "Mixed Produce Box", "A mixed selection of fruit, vegetables and seasonal produce.", "BX", "15.00"),
    ("Seasonal", "Summer Salad Box", "A seasonal salad box with leaves and fresh vegetables.", "BX", "10.50"),
    ("Seasonal", "Soup Pack", "A seasonal pack of vegetables suitable for soups and stews.", "PK", "6.50"),
]


STORAGE_GUIDANCE = [
    "Store in a cool, dry place away from direct sunlight.",
    "Keep refrigerated and consume before the expiry date.",
    "Store chilled and keep sealed after opening.",
    "Best stored in a ventilated vegetable drawer.",
    "Keep refrigerated between 0°C and 5°C.",
]


class Command(BaseCommand):
    help = "Populate the database with dummy products and inventory batches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of products to create. Default: 50.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing products before creating new ones.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        if count < 1:
            raise CommandError("--count must be greater than 0.")

        producers = list(Producer.objects.all())

        if not producers:
            raise CommandError(
                "No producers found. Create producer accounts before adding products."
            )

        if clear:
            deleted_count, _ = Product.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing product data. Deleted rows: {deleted_count}"
                )
            )

        categories = self._ensure_categories()

        created_products = 0
        created_inventory_batches = 0
        created_wholesale_tiers = 0

        for index in range(count):
            seed = PRODUCT_SEEDS[index % len(PRODUCT_SEEDS)]

            product = self._create_product(
                seed=seed,
                index=index,
                categories=categories,
                producers=producers,
            )
            created_products += 1

            inventory = self._create_inventory(product=product)
            created_inventory_batches += 1

            if random.choice([True, False]):
                self._create_wholesale_tier(product=product)
                created_wholesale_tiers += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Product population complete: "
                f"{created_products} products, "
                f"{created_inventory_batches} inventory batches, "
                f"{created_wholesale_tiers} wholesale tiers."
            )
        )

    def _ensure_categories(self):
        categories = {}

        for seed in CATEGORY_SEEDS:
            category = Category.objects.filter(name__iexact=seed["name"]).first()

            if category is None:
                category = Category.objects.create(**seed)
            else:
                category.food_groups = seed["food_groups"]
                category.description = category.description or seed["description"]
                category.vat = seed["vat"]
                category.save(update_fields=["food_groups", "description", "vat"])

            categories[seed["name"]] = category

        return categories

    def _create_product(self, seed, index, categories, producers):
        category_name, base_name, description, unit, price = seed

        producer = producers[index % len(producers)]
        category = categories[category_name]

        product_name = self._build_product_name(base_name=base_name, index=index)
        product_type = get_or_create_inferred_product_type(
            name=product_name,
            category=category,
        )

        return Product.objects.create(
            producer=producer,
            category=category,
            product_type=product_type,
            name=product_name,
            description=description,
            price=self._vary_price(price),
            unit=unit,
            low_stock_threshold=random.randint(5, 15),
            farm_origin=self._get_farm_origin(producer=producer),
            organic_certification_status=random.choice(
                [
                    Product.OrganicStatus.CERTIFIED,
                    Product.OrganicStatus.NOT_CERTIFIED,
                ]
            ),
            storage_guidance=random.choice(STORAGE_GUIDANCE),
            availability_status=Product.Availability_status.AVAILABLE,
            status=Product.Status.PUBLISHED,
        )

    def _create_inventory(self, product):
        today = timezone.localdate()

        original_quantity = random.randint(40, 180)
        remaining_quantity = random.randint(20, original_quantity)

        harvest_date = today - timedelta(days=random.randint(1, 10))
        expiry_date = today + timedelta(days=random.randint(10, 45))

        surplus_enabled = random.choice([True, False, False])

        if surplus_enabled:
            surplus_status = Inventory.SurplusStatus.SURPLUS_ACTIVE
            surplus_discount_percentage = Decimal(random.choice(["10.00", "15.00", "20.00"]))
            surplus_expiry = timezone.now() + timedelta(days=random.randint(2, 7))
            surplus_note = "Discount applied to help clear excess stock."
        else:
            surplus_status = Inventory.SurplusStatus.NONE
            surplus_discount_percentage = None
            surplus_expiry = None
            surplus_note = None

        return Inventory.objects.create(
            product=product,
            user=self._get_inventory_user(product.producer),
            original_quantity=original_quantity,
            remaining_quantity=remaining_quantity,
            harvest_date=harvest_date,
            expiry_date=expiry_date,
            expiry_type=random.choice(
                [
                    Inventory.ExpiryType.BEST_BEFORE,
                    Inventory.ExpiryType.USE_BY,
                ]
            ),
            surplus_status=surplus_status,
            surplus_discount_percentage=surplus_discount_percentage,
            surplus_expiry=surplus_expiry,
            surplus_note=surplus_note,
            status=Inventory.BatchStatus.ACTIVE,
        )

    def _create_wholesale_tier(self, product):
        discount_amount = Decimal(random.choice(["0.20", "0.35", "0.50", "0.75"]))
        wholesale_price = product.price - discount_amount

        if wholesale_price <= Decimal("0.10"):
            wholesale_price = product.price

        return WholesalePrice.objects.create(
            product=product,
            min_quantity=random.choice([10, 15, 20, 25]),
            unit_price=wholesale_price.quantize(Decimal("0.01")),
        )

    def _build_product_name(self, base_name, index):
        suffixes = [
            "Local",
            "Fresh",
            "Farmhouse",
            "Seasonal",
            "Premium",
            "Traditional",
        ]

        suffix = suffixes[index % len(suffixes)]

        return f"{suffix} {base_name}"

    def _vary_price(self, price):
        base_price = Decimal(price)
        variation = Decimal(random.choice(["0.00", "0.10", "0.20", "0.30", "0.40"]))

        return (base_price + variation).quantize(Decimal("0.01"))

    def _get_farm_origin(self, producer):
        farm_name = (
            getattr(producer, "farm_name", None)
            or getattr(producer, "business_name", None)
            or getattr(producer, "company_name", None)
        )

        if farm_name:
            return str(farm_name)[:150]

        return f"Producer {producer.pk} Farm"

    def _get_inventory_user(self, producer):
        return getattr(producer, "user", None)