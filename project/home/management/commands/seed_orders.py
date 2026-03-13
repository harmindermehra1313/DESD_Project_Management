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
    help = "Seeds additional targeted order-history data using the existing seed_database records."

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

        self.Order = apps.get_model("orders", "Order")
        self.OrderItem = apps.get_model("orders", "OrderItem")
        self.ProducerOrderSummary = apps.get_model("orders", "ProducerOrderSummary")
        self.ProducerOrderStatusHistory = apps.get_model("orders", "ProducerOrderStatusHistory")
        self.RecurringOrder = apps.get_model("orders", "RecurringOrder")

        self.customer_email = options["email"]
        self.pagination_count = options["count"]

        if self.pagination_count < 0:
            raise CommandError("--count must be 0 or greater.")

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding additional order history test data..."))

        self.load_existing_seed_data()
        self.create_second_customer()
        self.create_targeted_orders()
        self.create_pagination_orders()

        self.stdout.write(self.style.SUCCESS("Additional order history test data seeded successfully."))

    # -------------------------------------------------------------------------
    # Load existing data from seed_database
    # -------------------------------------------------------------------------
    def load_existing_seed_data(self):
        """
        Load the records created by seed_database.py.

        Purpose:
        - Reuse the existing base dataset
        - Avoid recreating all users, producers, products, and inventory
        - Extend the database with order-history-specific test scenarios
        """

        try:
            self.customer_user = self.User.objects.get(email=self.customer_email)
        except self.User.DoesNotExist as exc:
            raise CommandError(
                f"Customer with email '{self.customer_email}' was not found. "
                "Run 'python manage.py seed_database' first or provide an existing seeded email."
            ) from exc

        self.customer_address = self.Address.objects.filter(user=self.customer_user).first()
        if not self.customer_address:
            raise CommandError(f"Address not found for customer '{self.customer_email}'.")

        try:
            self.producer = self.Producer.objects.get(farm_name="Blue Cow Farm")
            self.producer2 = self.Producer.objects.get(farm_name="Cricket Ranch")
        except self.Producer.DoesNotExist as exc:
            raise CommandError(
                "Required producers were not found. Run 'python manage.py seed_database' first."
            ) from exc

        try:
            self.product1 = self.Product.objects.get(name="Organic Carrots")
            self.product2 = self.Product.objects.get(name="Free-range Eggs")
            self.product3 = self.Product.objects.get(name="Braeburn Apples")
        except self.Product.DoesNotExist as exc:
            raise CommandError(
                "Required products were not found. Run 'python manage.py seed_database' first."
            ) from exc

        self.inventory1 = self.Inventory.objects.filter(product=self.product1).first()
        self.inventory2 = self.Inventory.objects.filter(product=self.product2).first()
        self.inventory3 = self.Inventory.objects.filter(product=self.product3).first()

        if not all([self.inventory1, self.inventory2, self.inventory3]):
            raise CommandError("One or more inventory records are missing. Run seed_database first.")

        self.recurring = self.RecurringOrder.objects.filter(user=self.customer_user).first()

        self.stdout.write(self.style.SUCCESS("  Existing seed data loaded."))

    # -------------------------------------------------------------------------
    # Create another customer for ownership / cross-user tests
    # -------------------------------------------------------------------------
    def create_second_customer(self):
        """
        Create a second customer and address used for:
        - order ownership tests
        - not-found-for-other-user tests
        """

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

    # -------------------------------------------------------------------------
    # Address helpers
    # -------------------------------------------------------------------------
    def get_summary_address_from_address(self, address):
        """
        Return producer summary address fields derived from an Address record.

        Purpose:
        - Keep delivery summary addresses aligned with the selected seeded customer
        - Avoid hardcoded delivery address literals in seeded delivery scenarios
        """
        return {
            "summary_address_line1": address.line1,
            "summary_address_line2": address.line2 or "",
            "summary_city": address.city,
            "summary_postcode": address.postcode,
        }

    # -------------------------------------------------------------------------
    # Create targeted orders
    # -------------------------------------------------------------------------
    def create_targeted_orders(self):
        """
        Create targeted order-history cases for manual API testing.

        Coverage:
        - completed / pending / cancelled / in progress
        - delivery / collection
        - recurring / non-recurring
        - producer filters
        - date range filters
        - multi-producer detail scenarios
        """

        today = timezone.now()
        created_count = 0
        customer_delivery_summary = self.get_summary_address_from_address(self.customer_address)
        other_delivery_summary = self.get_summary_address_from_address(self.other_address)

        # 1. Completed delivery order for producer 1
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

        # 2. Pending delivery order for producer 1
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

        # 3. Completed collection order for producer 2
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

        # 4. Cancelled order
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

        # 5. Recurring completed order
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

        # 6. Non-recurring collection order
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

        # 7. Multi-producer mixed DEL + COL
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

        # 8. Multi-producer all collection, same address
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

        # 9. Multi-producer all collection, different addresses
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

        # 10. Multi-producer same delivery date
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

        # 11. Multi-producer different delivery dates
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

        # 12. Order for other user
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

        self.stdout.write(self.style.SUCCESS(f"  Targeted order-history orders created: {created_count}"))

    # -------------------------------------------------------------------------
    # Create extra pagination orders
    # -------------------------------------------------------------------------
    def create_pagination_orders(self):
        """
        Create additional normal orders so the history endpoint has enough rows
        to test pagination and page size behaviour.
        """

        base_time = timezone.now() - timezone.timedelta(days=20)
        created_count = 0
        customer_delivery_summary = self.get_summary_address_from_address(self.customer_address)

        for i in range(self.pagination_count):
            product = [self.product1, self.product2, self.product3][i % 3]
            inventory = [self.inventory1, self.inventory2, self.inventory3][i % 3]
            producer = [self.producer, self.producer, self.producer2][i % 3]

            order_status = (
                self.Order.Status.COMPLETED
                if i % 2 == 0
                else self.Order.Status.PENDING
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
                quantity=(i % 3) + 1,
                delivery_or_collection=delivery_type,
                summary_status=summary_status,
                delivery_date=(base_time + timezone.timedelta(days=i + 2)).date(),
                delivery_time_slot="10:00-12:00",
                **summary_address,
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Pagination orders created: {created_count}"))

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
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
    ):
        """
        Create one order with:
        - one order item
        - one producer summary
        - one status history record
        """

        quantity_decimal = Decimal(str(quantity))
        unit_price = Decimal(str(product.price))
        subtotal = (unit_price * quantity_decimal).quantize(Decimal("0.01"))
        commission_total = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        vat_total = Decimal("0.00")
        final_total = subtotal
        food_miles_total = Decimal("3.00")

        order = self.Order.objects.create(
            user=user,
            delivery_address=address,
            billing_address=address,
            recurring_order=recurring_order,
            order_date=order_date,
            total_price=subtotal,
            total_discount=Decimal("0.00"),
            total_vat=vat_total,
            final_total_price=final_total,
            total_commission=commission_total,
            food_miles_total=food_miles_total,
            status=order_status,
        )

        item_commission = (unit_price * Decimal("0.05")).quantize(Decimal("0.01"))

        self.OrderItem.objects.create(
            order=order,
            inventory=inventory,
            product=product,
            producer=producer,
            quantity=quantity,
            original_unit_price=unit_price,
            commission_amount=item_commission,
            discount_amount=Decimal("0.00"),
            discount_reason="",
            vat_amount=Decimal("0.00"),
            vat_rate=Decimal("0.00"),
            final_unit_price=unit_price,
            food_miles=Decimal("1.50"),
            preparation_deadline=order_date + timezone.timedelta(hours=4),
        )

        summary = self.ProducerOrderSummary.objects.create(
            order=order,
            producer=producer,
            subtotal=subtotal,
            commission_total=commission_total,
            vat_total=vat_total,
            payout_amount=(subtotal - commission_total).quantize(Decimal("0.01")),
            delivery_date=delivery_date,
            delivery_or_collection=delivery_or_collection,
            delivery_time_slot=delivery_time_slot,
            address_line1=summary_address_line1,
            address_line2=summary_address_line2,
            city=summary_city,
            postcode=summary_postcode,
            special_instructions="Seeded order history test data",
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
    ):
        """
        Create one multi-producer order with:
        - multiple order items
        - one producer summary per producer
        - one history row per producer summary
        """

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
        total_commission = Decimal("0.00")
        total_food_miles = Decimal("0.00")

        summary_data = {}

        for item in items:
            product = item["product"]
            inventory = item["inventory"]
            producer = item["producer"]
            quantity = item["quantity"]
            quantity_decimal = Decimal(str(quantity))

            unit_price = Decimal(str(product.price))
            line_subtotal = (unit_price * quantity_decimal).quantize(Decimal("0.01"))
            line_commission = (line_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
            line_food_miles = Decimal("1.50")

            self.OrderItem.objects.create(
                order=order,
                inventory=inventory,
                product=product,
                producer=producer,
                quantity=quantity,
                original_unit_price=unit_price,
                commission_amount=(unit_price * Decimal("0.05")).quantize(Decimal("0.01")),
                discount_amount=Decimal("0.00"),
                discount_reason="",
                vat_amount=Decimal("0.00"),
                vat_rate=Decimal("0.00"),
                final_unit_price=unit_price,
                food_miles=line_food_miles,
                preparation_deadline=order_date + timezone.timedelta(hours=4),
            )

            total_price += line_subtotal
            total_commission += line_commission
            total_food_miles += line_food_miles

            summary_data[producer.pk] = {
                "producer": producer,
                "subtotal": line_subtotal,
                "commission_total": line_commission,
                "vat_total": Decimal("0.00"),
                "payout_amount": (line_subtotal - line_commission).quantize(Decimal("0.01")),
                "delivery_date": item["delivery_date"],
                "delivery_or_collection": item["delivery_or_collection"],
                "delivery_time_slot": item["delivery_time_slot"],
                "address_line1": item["summary_address_line1"],
                "address_line2": item["summary_address_line2"],
                "city": item["summary_city"],
                "postcode": item["summary_postcode"],
                "status": item["summary_status"],
            }

        order.total_price = total_price.quantize(Decimal("0.01"))
        order.total_discount = Decimal("0.00")
        order.total_vat = Decimal("0.00")
        order.final_total_price = total_price.quantize(Decimal("0.01"))
        order.total_commission = total_commission.quantize(Decimal("0.01"))
        order.food_miles_total = total_food_miles.quantize(Decimal("0.01"))
        order.save()

        for data in summary_data.values():
            summary = self.ProducerOrderSummary.objects.create(
                order=order,
                producer=data["producer"],
                subtotal=data["subtotal"],
                commission_total=data["commission_total"],
                vat_total=data["vat_total"],
                payout_amount=data["payout_amount"],
                delivery_date=data["delivery_date"],
                delivery_or_collection=data["delivery_or_collection"],
                delivery_time_slot=data["delivery_time_slot"],
                address_line1=data["address_line1"],
                address_line2=data["address_line2"],
                city=data["city"],
                postcode=data["postcode"],
                special_instructions="Seeded multi-producer order history test data",
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