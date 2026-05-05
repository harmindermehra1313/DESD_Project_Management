from django.core.management.base import BaseCommand
from products.models import Allergen

class Command(BaseCommand):
    help = "Seed the database with all UK allergens"

    def handle(self, *args, **kwargs):
        created = 0
        skipped = 0

        for code, label in Allergen.Allergens.choices:
            if Allergen.objects.filter(name=code).exists():
                skipped += 1
                continue

            Allergen.objects.create(name=code)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Allergen seeding complete: {created} created, {skipped} skipped."
            )
        )