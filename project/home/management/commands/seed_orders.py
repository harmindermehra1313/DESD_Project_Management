# docker compose exec web python manage.py seed_orders --email mark42@hotmail.com --count 25
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Address
from orders.models import Order

User = get_user_model()


class Command(BaseCommand):
    """
    Create fake orders for pagination testing.

    Purpose:
    - Generate multiple orders for a specific user
    - Allow API pagination endpoints to be tested
    """

    help = "Seed orders for pagination testing"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, required=True)
        parser.add_argument("--count", type=int, default=25)

    def handle(self, *args, **options):

        email = options["email"]
        count = options["count"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError("User not found")

        address = Address.objects.filter(user=user).first()

        if not address:
            raise CommandError("User must have an address first")

        statuses = [
            Order.Status.PENDING,
            Order.Status.IN_PROGRESS,
            Order.Status.OUT_FOR_DELIVERY,
            Order.Status.READY_FOR_COLLECTION,
            Order.Status.COMPLETED,
            Order.Status.CANCELLED,
        ]

        for i in range(count):

            Order.objects.create(
                user=user,
                delivery_address=address,
                billing_address=address,
                order_date=timezone.now() - timedelta(days=i),
                total_price=Decimal("10.00"),
                total_discount=Decimal("0.00"),
                total_vat=Decimal("2.00"),
                final_total_price=Decimal("12.00"),
                total_commission=Decimal("1.00"),
                food_miles_total=Decimal("15.00"),
                status=random.choice(statuses),
            )

        self.stdout.write(
            self.style.SUCCESS(f"{count} orders created for {email}")
        )