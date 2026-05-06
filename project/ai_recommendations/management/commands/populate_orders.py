# docker compose exec web python manage.py populate_orders --count 2500 --clear
import random
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from orders.models import Order, OrderItem, ProducerOrderSummary
from products.models import Inventory, Product

UK_DEMO_ADDRESSES = [
    {
        "line1": "12 Gloucester Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS7 8AE",
    },
    {
        "line1": "45 North Street",
        "line2": "Bedminster",
        "city": "Bristol",
        "postcode": "BS3 1EN",
    },
    {
        "line1": "88 Whiteladies Road",
        "line2": "Clifton",
        "city": "Bristol",
        "postcode": "BS8 2QX",
    },
    {
        "line1": "19 Stokes Croft",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS1 3PY",
    },
    {
        "line1": "7 East Street",
        "line2": "Old Market",
        "city": "Bristol",
        "postcode": "BS2 0BH",
    },
    {
        "line1": "61 Church Road",
        "line2": "Redfield",
        "city": "Bristol",
        "postcode": "BS5 9JR",
    },
    {
        "line1": "104 Wells Road",
        "line2": "Knowle",
        "city": "Bristol",
        "postcode": "BS4 2AL",
    },
    {
        "line1": "23 High Street",
        "line2": "",
        "city": "Bath",
        "postcode": "BA1 5AJ",
    },
]


PRODUCER_STATUS_SCENARIO_WEIGHTS = [
    ("all_pending", 20),
    ("in_progress", 60),
    ("all_shipped", 20),
]


COMMISSION_RATE = Decimal("0.10")


class Command(BaseCommand):
    help = "Populate the database with dummy customer orders and order items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Number of orders to create. Default: 100.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing orders before creating new ones.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        if count < 1:
            raise CommandError("--count must be greater than 0.")

        customers = self._get_customer_users()

        if not customers:
            raise CommandError(
                "No customer users found. Create customer demo users first."
            )

        inventories = self._get_available_inventories()

        if not inventories:
            raise CommandError(
                "No available product inventory found. Run populate_products first."
            )

        if clear:
            deleted_count, _ = Order.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing order data. Deleted rows: {deleted_count}"
                )
            )

        created_orders = 0
        created_items = 0
        created_summaries = 0

        for index in range(count):
            with transaction.atomic():
                order, item_count, summary_count = self._create_order(
                    index=index,
                    customers=customers,
                    inventories=inventories,
                )

            created_orders += 1
            created_items += item_count
            created_summaries += summary_count

            self.stdout.write(f"Created order #{order.pk} for {order.user.email}")

        self.stdout.write(
            self.style.SUCCESS(
                "Order population complete: "
                f"{created_orders} orders, "
                f"{created_items} order items, "
                f"{created_summaries} producer summaries."
            )
        )

    def _get_customer_users(self):
        User = get_user_model()
        users = list(User.objects.filter(is_active=True).order_by("id"))

        customer_users = []

        for user in users:
            if self._looks_like_customer(user):
                customer_users.append(user)

        if customer_users:
            return customer_users

        return list(
            User.objects.filter(
                is_active=True,
                is_staff=False,
                is_superuser=False,
            ).order_by("id")
        )

    def _looks_like_customer(self, user):
        role = str(getattr(user, "role", "") or "").upper()

        if role in {"CUSTOMER", "CUS", "C"}:
            return True

        try:
            return getattr(user, "customer_profile", None) is not None
        except Exception:
            return False

    def _get_available_inventories(self):
        today = timezone.localdate()

        return list(
            Inventory.objects.select_related(
                "product",
                "product__producer",
                "product__category",
            )
            .filter(
                status=Inventory.BatchStatus.ACTIVE,
                remaining_quantity__gt=0,
                expiry_date__gte=today,
                product__status=Product.Status.PUBLISHED,
                product__availability_status=Product.Availability_status.AVAILABLE,
            )
            .order_by("product_id", "expiry_date")
        )

    def _create_order(self, index, customers, inventories):
        customer = customers[index % len(customers)]
        address = self._get_or_create_address(user=customer, index=index)

        order_date = timezone.now() - timedelta(days=random.randint(1, 90))

        order = Order.objects.create(
            user=customer,
            delivery_address=address,
            billing_address=address,
            order_date=order_date,
            status=Order.Status.PENDING,
            is_guest=False,
        )

        selected_inventories = random.sample(
            inventories,
            k=min(random.randint(1, 5), len(inventories)),
        )

        totals = {
            "total_price": Decimal("0.00"),
            "total_discount": Decimal("0.00"),
            "total_vat": Decimal("0.00"),
            "final_total_price": Decimal("0.00"),
            "total_commission": Decimal("0.00"),
            "food_miles_total": Decimal("0.00"),
        }

        producer_totals = {}

        created_items = 0

        for inventory in selected_inventories:
            item_totals = self._create_order_item(
                order=order,
                inventory=inventory,
                order_date=order_date,
            )

            created_items += 1

            for key in totals:
                totals[key] += item_totals[key]

            producer = inventory.product.producer

            if producer.pk not in producer_totals:
                producer_totals[producer.pk] = {
                    "producer": producer,
                    "subtotal": Decimal("0.00"),
                    "commission_total": Decimal("0.00"),
                    "vat_total": Decimal("0.00"),
                    "food_miles_total": Decimal("0.00"),
                }

            producer_totals[producer.pk]["subtotal"] += item_totals[
                "line_final_subtotal"
            ]
            producer_totals[producer.pk]["commission_total"] += item_totals[
                "total_commission"
            ]
            producer_totals[producer.pk]["vat_total"] += item_totals["total_vat"]
            producer_totals[producer.pk]["food_miles_total"] += item_totals[
                "food_miles_total"
            ]

        order.total_price = self._money(totals["total_price"])
        order.total_discount = self._money(totals["total_discount"])
        order.total_vat = self._money(totals["total_vat"])
        order.final_total_price = self._money(totals["final_total_price"])
        order.total_commission = self._money(totals["total_commission"])
        order.food_miles_total = self._money(totals["food_miles_total"])
        order.save(
            update_fields=[
                "total_price",
                "total_discount",
                "total_vat",
                "final_total_price",
                "total_commission",
                "food_miles_total",
            ]
        )

        created_summaries, producer_summary_statuses = self._create_producer_summaries(
            order=order,
            address=address,
            order_date=order_date,
            producer_totals=producer_totals,
        )

        order.status = self._derive_order_status_from_producer_summaries(
            producer_summary_statuses
        )
        order.save(update_fields=["status"])

        return order, created_items, created_summaries

    def _create_order_item(self, order, inventory, order_date):
        product = inventory.product
        quantity = random.randint(1, min(5, inventory.remaining_quantity))

        original_unit_price = self._money(product.price)
        final_unit_price = self._money(inventory.get_discounted_price())

        unit_discount = max(
            Decimal("0.00"),
            original_unit_price - final_unit_price,
        )

        line_original_subtotal = original_unit_price * quantity
        line_final_subtotal = final_unit_price * quantity
        line_discount_total = unit_discount * quantity

        vat_rate = self._money(getattr(product.category, "vat", Decimal("0.00")))
        vat_amount = self._money(line_final_subtotal * vat_rate / Decimal("100.00"))

        commission_amount = self._money(line_final_subtotal * COMMISSION_RATE)
        food_miles = self._money(Decimal(random.randint(2, 45)))

        if unit_discount > 0:
            discount_reason = "Surplus discount applied."
        else:
            discount_reason = ""

        OrderItem.objects.create(
            order=order,
            product=product,
            inventory=inventory,
            producer=product.producer,
            quantity=quantity,
            original_unit_price=original_unit_price,
            commission_amount=commission_amount,
            discount_amount=self._money(line_discount_total),
            discount_reason=discount_reason,
            vat_amount=vat_amount,
            vat_rate=vat_rate,
            final_unit_price=final_unit_price,
            food_miles=food_miles,
            preparation_deadline=order_date + timedelta(days=1),
        )

        return {
            "total_price": line_original_subtotal,
            "total_discount": line_discount_total,
            "total_vat": vat_amount,
            "final_total_price": line_final_subtotal + vat_amount,
            "total_commission": commission_amount,
            "food_miles_total": food_miles,
            "line_final_subtotal": line_final_subtotal,
        }

    def _create_producer_summaries(
        self,
        order,
        address,
        order_date,
        producer_totals,
    ):
        created = 0
        created_statuses = []

        scenario = self._weighted_choice(PRODUCER_STATUS_SCENARIO_WEIGHTS)
        producer_statuses = self._build_producer_summary_statuses(
            scenario=scenario,
            producer_count=len(producer_totals),
        )

        for index, data in enumerate(producer_totals.values()):
            subtotal = self._money(data["subtotal"])
            commission_total = self._money(data["commission_total"])
            vat_total = self._money(data["vat_total"])
            payout_amount = self._money(subtotal - commission_total)
            summary_status = producer_statuses[index]

            ProducerOrderSummary.objects.create(
                order=order,
                producer=data["producer"],
                subtotal=subtotal,
                commission_total=commission_total,
                vat_total=vat_total,
                payout_amount=payout_amount,
                delivery_date=(
                    order_date + timedelta(days=random.randint(1, 5))
                ).date(),
                delivery_or_collection=random.choice(
                    [
                        Order.DeliveryOrCollection.DELIVERY,
                        Order.DeliveryOrCollection.COLLECTION,
                    ]
                ),
                delivery_time_slot=random.choice(
                    [
                        "09:00-11:00",
                        "11:00-13:00",
                        "13:00-15:00",
                        "15:00-17:00",
                    ]
                ),
                address_line1=self._address_value(
                    address,
                    ["line1", "address_line1", "address1"],
                    "12 Gloucester Road",
                ),
                address_line2=self._address_value(
                    address,
                    ["line2", "address_line2", "address2"],
                    "",
                ),
                city=self._address_value(address, ["city", "town"], "Bristol"),
                postcode=self._address_value(
                    address,
                    ["postcode", "post_code", "postal_code"],
                    "BS1 1AA",
                ),
                special_instructions=random.choice(
                    [
                        "",
                        "Please leave with reception.",
                        "Ring the bell on arrival.",
                        "Call before delivery.",
                    ]
                ),
                status=summary_status,
            )

            created += 1
            created_statuses.append(summary_status)

        return created, created_statuses

    def _build_producer_summary_statuses(self, scenario, producer_count):
        """
        Build producer summary statuses first.

        The main order status is derived from these statuses afterwards.
        """
        if scenario == "all_pending":
            return [ProducerOrderSummary.Status.PENDING] * producer_count

        if scenario == "all_shipped":
            return [ProducerOrderSummary.Status.SHIPPED] * producer_count

        progress_statuses = [
            ProducerOrderSummary.Status.PREPARING,
            ProducerOrderSummary.Status.PACKAGED,
        ]

        statuses = []

        for _index in range(producer_count):
            statuses.append(random.choice(progress_statuses))

        if producer_count > 1:
            statuses[random.randrange(producer_count)] = random.choice(progress_statuses)

        return statuses

    def _derive_order_status_from_producer_summaries(self, producer_summary_statuses):
        """
        Derive the main order status from producer-level statuses.
    
        Rules:
        - all Pending -> Order Pending
        - all Shipped -> Order Completed
        - anything else -> Order In progress
        """
        if not producer_summary_statuses:
            return Order.Status.PENDING
    
        if all(
            status == ProducerOrderSummary.Status.PENDING
            for status in producer_summary_statuses
        ):
            return Order.Status.PENDING
    
        if all(
            status == ProducerOrderSummary.Status.SHIPPED
            for status in producer_summary_statuses
        ):
            return Order.Status.COMPLETED
    
        return Order.Status.IN_PROGRESS

    def _get_or_create_address(self, user, index):
        Address = apps.get_model("accounts", "Address")

        lookup = self._address_lookup_for_user(Address, user)

        if lookup:
            existing_address = Address.objects.filter(**lookup).first()

            if existing_address:
                return existing_address

        address_data = UK_DEMO_ADDRESSES[index % len(UK_DEMO_ADDRESSES)]
        kwargs = self._build_address_kwargs(
            Address=Address,
            user=user,
            address_data=address_data,
        )

        try:
            return Address.objects.create(**kwargs)
        except Exception as exc:
            raise CommandError(
                "Could not create a customer address. "
                "Check accounts.Address required fields. "
                f"Original error: {exc}"
            ) from exc

    def _address_lookup_for_user(self, Address, user):
        field_names = self._model_field_names(Address)

        if "user" in field_names:
            return {"user": user}

        customer_profile = self._customer_profile(user)

        if "customer" in field_names and customer_profile is not None:
            return {"customer": customer_profile}

        return {}

    def _build_address_kwargs(self, Address, user, address_data):
        kwargs = {}
        field_names = self._model_field_names(Address)

        field_map = {
            "line1": address_data["line1"],
            "address_line1": address_data["line1"],
            "address1": address_data["line1"],
            "line2": address_data["line2"],
            "address_line2": address_data["line2"],
            "address2": address_data["line2"],
            "city": address_data["city"],
            "town": address_data["city"],
            "postcode": address_data["postcode"],
            "post_code": address_data["postcode"],
            "postal_code": address_data["postcode"],
            "country": "United Kingdom",
            "phone": "07123456789",
            "is_default": True,
        }

        if "user" in field_names:
            kwargs["user"] = user

        customer_profile = self._customer_profile(user)

        if "customer" in field_names and customer_profile is not None:
            kwargs["customer"] = customer_profile

        for field_name, value in field_map.items():
            if field_name in field_names:
                kwargs[field_name] = value

        for field in Address._meta.fields:
            if field.name in kwargs:
                continue

            if self._can_skip_field(field):
                continue

            default_value = self._default_value_for_required_field(
                field=field,
                user=user,
            )

            if default_value is not None:
                kwargs[field.name] = default_value

        return kwargs

    def _default_value_for_required_field(self, field, user):
        if isinstance(field, models.CharField):
            return "Demo value"

        if isinstance(field, models.TextField):
            return ""

        if isinstance(field, models.EmailField):
            return getattr(user, "email", "demo@example.com")

        if isinstance(field, models.BooleanField):
            return False

        if isinstance(field, models.IntegerField):
            return 0

        if isinstance(field, models.DecimalField):
            return Decimal("0.00")

        if isinstance(field, models.DateTimeField):
            return timezone.now()

        if isinstance(field, models.DateField):
            return timezone.localdate()

        if isinstance(field, models.ForeignKey):
            related_model = field.remote_field.model

            if related_model == get_user_model():
                return user

            customer_profile = self._customer_profile(user)

            if (
                customer_profile is not None
                and customer_profile.__class__ == related_model
            ):
                return customer_profile

            return related_model.objects.first()

        return None

    def _can_skip_field(self, field):
        return (
            field.primary_key
            or field.auto_created
            or not field.editable
            or field.has_default()
            or field.null
            or field.blank
        )

    def _model_field_names(self, model_class):
        return {field.name for field in model_class._meta.get_fields()}

    def _customer_profile(self, user):
        try:
            return getattr(user, "customer_profile", None)
        except Exception:
            return None

    def _address_value(self, address, possible_fields, default):
        for field_name in possible_fields:
            if hasattr(address, field_name):
                value = getattr(address, field_name)

                if value:
                    return value

        return default

    def _weighted_choice(self, choices):
        values = [value for value, _weight in choices]
        weights = [weight for _value, weight in choices]

        return random.choices(values, weights=weights, k=1)[0]

    def _money(self, value):
        return Decimal(value).quantize(Decimal("0.01"))
