# docker compose exec web python manage.py populate_ai_interactions --count 2500 --clear --extra-events-per-user 75

import random
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from ai_recommendations.models import ProductInteraction
from orders.models import Order
from products.models import Inventory, Product


class Command(BaseCommand):
    help = "Populate AI recommendation interactions from demo order history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=None,
            help="Number of orders to convert into AI interactions. Default: all eligible orders.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Delete previous synthetic and order-history AI interactions "
                "before creating new ones. Existing web interactions are preserved."
            ),
        )
        parser.add_argument(
            "--extra-events-per-user",
            type=int,
            default=25,
            help=(
                "Number of extra synthetic view/add-to-cart events to create "
                "per user based on their ordered product types. Default: 25."
            ),
        )
        parser.add_argument(
            "--include-pending",
            action="store_true",
            help=(
                "Also use pending orders. Disabled by default because pending "
                "orders should not normally produce transaction-strength signals."
            ),
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]
        extra_events_per_user = options["extra_events_per_user"]
        include_pending = options["include_pending"]

        if count is not None and count < 1:
            raise CommandError("--count must be greater than 0.")

        if extra_events_per_user < 0:
            raise CommandError("--extra-events-per-user cannot be negative.")

        if clear:
            deleted_count, _ = ProductInteraction.objects.filter(
                source__in=[
                    ProductInteraction.Source.SYNTHETIC,
                    ProductInteraction.Source.ORDER_HISTORY,
                ]
            ).delete()

            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {deleted_count} previous AI demo interactions."
                )
            )

        live_products = list(
            self.get_live_products_queryset()
            .select_related("category", "product_type", "producer")
            .order_by("id")
        )

        if len(live_products) < 2:
            raise CommandError(
                "At least 2 live products are needed. Run populate_products first "
                "and check product status, availability, active inventory, stock "
                "and expiry dates."
            )

        live_product_by_id = {
            product.id: product
            for product in live_products
        }

        orders = self.get_orders_for_interactions(
            count=count,
            include_pending=include_pending,
        )

        if not orders:
            raise CommandError(
                "No eligible orders found. Run populate_orders first. "
                "Pending orders are ignored unless --include-pending is used."
            )

        user_product_ids = defaultdict(set)
        user_product_type_ids = defaultdict(set)
        user_category_ids = defaultdict(set)

        created_order_events = 0

        with transaction.atomic():
            for order in orders:
                created_order_events += self.create_order_history_interactions(
                    order=order,
                    live_product_by_id=live_product_by_id,
                    user_product_ids=user_product_ids,
                    user_product_type_ids=user_product_type_ids,
                    user_category_ids=user_category_ids,
                )

            created_extra_events = self.create_extra_preference_events(
                user_product_ids=user_product_ids,
                user_product_type_ids=user_product_type_ids,
                user_category_ids=user_category_ids,
                live_products=live_products,
                extra_events_per_user=extra_events_per_user,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "AI interaction population complete: "
                f"{created_order_events} order-derived events, "
                f"{created_extra_events} extra synthetic preference events."
            )
        )

        self.stdout.write(f"Orders used: {len(orders)}")
        self.stdout.write(f"Users with AI interactions: {len(user_product_ids)}")
        self.stdout.write(f"Live products available: {len(live_products)}")
        self.stdout.write("")
        self.stdout.write("Next step:")
        self.stdout.write("  docker compose exec web python manage.py train_ai_recommender_from_db")

    def get_live_products_queryset(self):
        today = timezone.localdate()

        active_inventory = Inventory.objects.filter(
            product_id=OuterRef("pk"),
            status=Inventory.BatchStatus.ACTIVE,
            remaining_quantity__gt=0,
            expiry_date__gte=today,
        )

        return (
            Product.objects.filter(
                status=Product.Status.PUBLISHED,
                availability_status=Product.Availability_status.AVAILABLE,
            )
            .annotate(has_active_inventory=Exists(active_inventory))
            .filter(has_active_inventory=True)
        )

    def get_orders_for_interactions(self, count, include_pending):
        allowed_statuses = [
            Order.Status.IN_PROGRESS,
            Order.Status.COMPLETED,
        ]

        if include_pending:
            allowed_statuses.append(Order.Status.PENDING)

        queryset = (
            Order.objects.filter(
                user__isnull=False,
                items__isnull=False,
                status__in=allowed_statuses,
                final_total_price__gt=0,
            )
            .select_related("user")
            .prefetch_related(
                "items",
                "items__product",
                "items__product__category",
                "items__product__product_type",
                "items__product__producer",
            )
            .distinct()
            .order_by("order_date", "id")
        )

        if count is not None:
            queryset = queryset[:count]

        return list(queryset)

    def create_order_history_interactions(
        self,
        order,
        live_product_by_id,
        user_product_ids,
        user_product_type_ids,
        user_category_ids,
    ):
        created_count = 0

        for item in order.items.all():
            product = live_product_by_id.get(item.product_id)

            if product is None:
                continue

            self.create_interaction(
                user=order.user,
                product=product,
                event_type=ProductInteraction.EventType.VIEW,
                source=ProductInteraction.Source.SYNTHETIC,
                created_at=order.order_date - timedelta(
                    hours=random.randint(2, 12),
                    minutes=random.randint(0, 59),
                ),
            )
            created_count += 1

            self.create_interaction(
                user=order.user,
                product=product,
                event_type=ProductInteraction.EventType.ADD_TO_CART,
                source=ProductInteraction.Source.SYNTHETIC,
                created_at=order.order_date - timedelta(
                    minutes=random.randint(15, 90),
                ),
            )
            created_count += 1

            self.create_interaction(
                user=order.user,
                product=product,
                event_type=ProductInteraction.EventType.TRANSACTION,
                source=ProductInteraction.Source.ORDER_HISTORY,
                created_at=order.order_date,
            )
            created_count += 1

            user_product_ids[order.user_id].add(product.id)

            if product.product_type_id:
                user_product_type_ids[order.user_id].add(product.product_type_id)

            if product.category_id:
                user_category_ids[order.user_id].add(product.category_id)

        return created_count

    def create_extra_preference_events(
        self,
        user_product_ids,
        user_product_type_ids,
        user_category_ids,
        live_products,
        extra_events_per_user,
    ):
        if extra_events_per_user == 0:
            return 0

        products_by_type = defaultdict(list)
        products_by_category = defaultdict(list)

        for product in live_products:
            if product.product_type_id:
                products_by_type[product.product_type_id].append(product)

            if product.category_id:
                products_by_category[product.category_id].append(product)

        created_count = 0

        for user_id in user_product_ids:
            candidate_products = self.get_candidate_products_for_user(
                user_id=user_id,
                user_product_ids=user_product_ids,
                user_product_type_ids=user_product_type_ids,
                user_category_ids=user_category_ids,
                products_by_type=products_by_type,
                products_by_category=products_by_category,
                live_products=live_products,
            )

            if not candidate_products:
                continue

            for _index in range(extra_events_per_user):
                product = random.choice(candidate_products)

                event_type = random.choices(
                    [
                        ProductInteraction.EventType.VIEW,
                        ProductInteraction.EventType.ADD_TO_CART,
                    ],
                    weights=[80, 20],
                    k=1,
                )[0]

                ProductInteraction.objects.create(
                    user_id=user_id,
                    session_key="",
                    product=product,
                    event_type=event_type,
                    source=ProductInteraction.Source.SYNTHETIC,
                    created_at=timezone.now()
                    - timedelta(
                        days=random.randint(0, 21),
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                    ),
                )

                created_count += 1

        return created_count

    def get_candidate_products_for_user(
        self,
        user_id,
        user_product_ids,
        user_product_type_ids,
        user_category_ids,
        products_by_type,
        products_by_category,
        live_products,
    ):
        already_ordered_ids = user_product_ids[user_id]
        candidates = []

        for product_type_id in user_product_type_ids[user_id]:
            candidates.extend(products_by_type.get(product_type_id, []))

        if not candidates:
            for category_id in user_category_ids[user_id]:
                candidates.extend(products_by_category.get(category_id, []))

        if not candidates:
            candidates = live_products

        filtered_candidates = [
            product
            for product in candidates
            if product.id not in already_ordered_ids
        ]

        if filtered_candidates:
            return filtered_candidates

        return list(candidates)

    def create_interaction(self, user, product, event_type, source, created_at):
        ProductInteraction.objects.create(
            user=user,
            session_key="",
            product=product,
            event_type=event_type,
            source=source,
            created_at=created_at,
        )