# docker compose exec web python manage.py train_ai_recommender_from_db
import json
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone
from implicit.als import AlternatingLeastSquares
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from ai_recommendations.models import ProductInteraction
from orders.models import Order, OrderItem
from products.models import Inventory, Product


class Command(BaseCommand):
    help = "Train TF-IDF and ALS recommendation models from the Django database."

    def add_arguments(self, parser):
        parser.add_argument("--factors", type=int, default=32)
        parser.add_argument("--iterations", type=int, default=20)
        parser.add_argument("--regularization", type=float, default=0.1)

    def handle(self, *args, **options):
        artifact_dir = Path(settings.BASE_DIR) / "ai_recommendations" / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        products = list(
            self.get_live_products_queryset()
            .select_related("producer", "category", "product_type")
            .order_by("id")
        )

        if not products:
            self.stdout.write(self.style.ERROR("No live products found."))
            return

        product_id_to_idx = {
            product.id: index for index, product in enumerate(products)
        }
        idx_to_product_id = {
            index: product_id for product_id, index in product_id_to_idx.items()
        }

        product_texts = [self.build_product_text(product) for product in products]

        tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words="english",
        )
        tfidf_matrix = tfidf_vectorizer.fit_transform(product_texts)

        interaction_rows = self.collect_interactions(product_id_to_idx)

        if not interaction_rows:
            self.stdout.write(
                self.style.WARNING(
                    "No logged-in interactions or completed orders found. "
                    "TF-IDF was trained, but ALS could not be trained."
                )
            )

            user_id_to_idx = {}
            user_item_matrix = sparse.csr_matrix(
                (0, len(products)),
                dtype=np.float32,
            )
            als_user_factors = np.zeros((0, options["factors"]))
            als_item_factors = np.zeros((len(products), options["factors"]))
            als_available = False

        else:
            user_ids = sorted({row["user_id"] for row in interaction_rows})
            user_id_to_idx = {user_id: index for index, user_id in enumerate(user_ids)}

            row_indices = []
            col_indices = []
            values = []

            for row in interaction_rows:
                row_indices.append(user_id_to_idx[row["user_id"]])
                col_indices.append(product_id_to_idx[row["product_id"]])
                values.append(row["weight"])

            user_item_matrix = sparse.csr_matrix(
                (values, (row_indices, col_indices)),
                shape=(len(user_ids), len(products)),
                dtype=np.float32,
            )
            user_item_matrix.sum_duplicates()

            als_model = AlternatingLeastSquares(
                factors=options["factors"],
                regularization=options["regularization"],
                iterations=options["iterations"],
                random_state=42,
            )

            als_model.fit(user_item_matrix)

            als_user_factors = als_model.user_factors
            als_item_factors = als_model.item_factors
            als_available = True

        sparse.save_npz(artifact_dir / "tfidf_matrix.npz", tfidf_matrix)
        sparse.save_npz(artifact_dir / "user_item_matrix.npz", user_item_matrix)

        np.save(artifact_dir / "als_user_factors.npy", als_user_factors)
        np.save(artifact_dir / "als_item_factors.npy", als_item_factors)

        joblib.dump(tfidf_vectorizer, artifact_dir / "tfidf_vectorizer.joblib")
        joblib.dump(user_id_to_idx, artifact_dir / "user_id_to_idx.joblib")
        joblib.dump(product_id_to_idx, artifact_dir / "product_id_to_idx.joblib")
        joblib.dump(idx_to_product_id, artifact_dir / "idx_to_product_id.joblib")

        metadata = {
            "product_count": len(products),
            "interaction_count": len(interaction_rows),
            "user_count": len(user_id_to_idx),
            "als_available": als_available,
            "factors": options["factors"],
            "iterations": options["iterations"],
            "regularization": options["regularization"],
        }

        with open(artifact_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS("AI recommender trained from Django database.")
        )
        self.stdout.write(f"Products:      {metadata['product_count']}")
        self.stdout.write(f"Users:         {metadata['user_count']}")
        self.stdout.write(f"Interactions:  {metadata['interaction_count']}")
        self.stdout.write(f"ALS available: {metadata['als_available']}")
        self.stdout.write(f"Artefacts:     {artifact_dir}")

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

    def build_product_text(self, product):
        category = product.category
        product_type = product.product_type
        producer = product.producer

        parts = [
            product.name,
            product.description,
            product.farm_origin,
            product.storage_guidance,
            category.name if category else "",
            product_type.name if product_type else "",
            producer.farm_name if producer else "",
        ]

        return " ".join(str(part) for part in parts if part)

    def collect_interactions(self, product_id_to_idx):
        rows = []
        valid_product_ids = set(product_id_to_idx.keys())

        interactions = ProductInteraction.objects.filter(
            user__isnull=False,
            product_id__in=valid_product_ids,
        ).values("user_id", "product_id", "event_type")

        for interaction in interactions:
            rows.append(
                {
                    "user_id": interaction["user_id"],
                    "product_id": interaction["product_id"],
                    "weight": ProductInteraction.weight_for_event(
                        interaction["event_type"]
                    ),
                }
            )

        completed_items = (
            OrderItem.objects.filter(
                order__user__isnull=False,
                order__status=Order.Status.COMPLETED,
                product_id__in=valid_product_ids,
            )
            .values("order__user_id", "product_id")
            .annotate(quantity_total=Sum("quantity"))
        )

        transaction_weight = ProductInteraction.weight_for_event(
            ProductInteraction.EventType.TRANSACTION
        )

        for item in completed_items:
            rows.append(
                {
                    "user_id": item["order__user_id"],
                    "product_id": item["product_id"],
                    "weight": float(item["quantity_total"] or 1) * transaction_weight,
                }
            )

        return rows
