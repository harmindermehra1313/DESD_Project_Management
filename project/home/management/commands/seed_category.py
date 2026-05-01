from django.core.management.base import BaseCommand
from products.models import Category
from decimal import Decimal

class Command(BaseCommand):
    help = "Bulk seed all default product categories"

    DEFAULT_CATEGORIES = [
        {
            "name": "Meat",
            "food_groups": "MT",
            "description": "Fresh and processed meat products",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Dairy",
            "food_groups": "DA",
            "description": "Milk, cheese, yoghurt, butter and dairy products",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Eggs",
            "food_groups": "EG",
            "description": "Eggs from hens, ducks, and other poultry",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Fruit",
            "food_groups": "FR",
            "description": "Fresh fruit and orchard produce",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Vegetables",
            "food_groups": "VEG",
            "description": "Fresh vegetables, roots, and leafy greens",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Bread & Bakery",
            "food_groups": "BAK",
            "description": "Fresh bread, pastries, cakes, and baked goods",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Preserves & Jams",
            "food_groups": "PRE",
            "description": "Jams, chutneys, marmalades, and fruit preserves",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Pickled & Fermented",
            "food_groups": "PIC",
            "description": "Pickled vegetables, kimchi, sauerkraut, and fermented foods",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Honey & Syrups",
            "food_groups": "SWT",
            "description": "Local honey, maple syrup, and natural sweeteners",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Juices & Beverages",
            "food_groups": "BEV",
            "description": "Fresh juices, cordials, and non‑alcoholic drinks",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Snacks & Confectionery",
            "food_groups": "SNK",
            "description": "Handmade snacks, sweets, and confectionery items",
            "vat": Decimal("0.00"),
        },
        {
            "name": "Artisan Goods",
            "food_groups": "ART",
            "description": "Miscellaneous handmade or small‑batch food products",
            "vat": Decimal("0.00"),
        },
    ]

    def handle(self, *args, **kwargs):
        created = 0
        skipped = 0

        for cat in self.DEFAULT_CATEGORIES:
            if Category.objects.filter(name=cat["name"]).exists():
                skipped += 1
                continue

            Category.objects.create(**cat)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete: {created} created, {skipped} skipped (already existed)."
            )
        )
