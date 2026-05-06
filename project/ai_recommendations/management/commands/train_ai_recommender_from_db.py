# docker compose exec web python manage.py train_ai_recommender_from_db

"""
Train TF-IDF and ALS recommendation artefacts from the Django database.

Important:
Thread limits are configured before importing NumPy, SciPy, scikit-learn, or
implicit. This avoids OpenBLAS creating a large internal thread pool during
ALS training.
"""

import os


def configure_blas_threads():
    """
    Keep BLAS libraries single-threaded.

    implicit ALS performs its own threaded work. Allowing OpenBLAS/MKL/OMP to
    create their own thread pools at the same time can slow training down,
    especially on older laptops or small Docker containers.
    """
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


configure_blas_threads()

import json
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone
from implicit.als import AlternatingLeastSquares
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from ai_recommendations.models import ProductInteraction
from orders.models import Order, OrderItem
from products.models import Inventory, Product


DEFAULT_MAX_TFIDF_FEATURES = 5000
DEFAULT_RANDOM_STATE = 42


def choose_default_als_threads(cpu_count):
    """
    Choose a safe ALS thread count.

    os.cpu_count() normally returns logical CPUs, not physical cores.
    Older CPUs can become slow or noisy if every logical CPU is used.

    Conservative defaults:
    - 1-2 CPUs: 1 thread
    - 3-4 CPUs: 2 threads
    - 5-8 CPUs: 4 threads
    - 9+ CPUs: half, capped at 8
    """
    if cpu_count <= 2:
        return 1

    if cpu_count <= 4:
        return 2

    if cpu_count <= 8:
        return 4

    return min(8, max(1, cpu_count // 2))


class Command(BaseCommand):
    help = "Train TF-IDF and ALS recommendation models from the Django database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--factors",
            type=int,
            default=32,
            help="Number of ALS latent factors. Default: 32.",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=20,
            help="Number of ALS training iterations. Default: 20.",
        )
        parser.add_argument(
            "--regularization",
            type=float,
            default=0.1,
            help="ALS regularization value. Default: 0.1.",
        )
        parser.add_argument(
            "--als-threads",
            type=int,
            default=None,
            help=(
                "Number of ALS training threads. "
                "Overrides RECOMMENDER_ALS_THREADS and auto-detection."
            ),
        )
        parser.add_argument(
            "--max-features",
            type=int,
            default=DEFAULT_MAX_TFIDF_FEATURES,
            help=f"Maximum TF-IDF features. Default: {DEFAULT_MAX_TFIDF_FEATURES}.",
        )

    def handle(self, *args, **options):
        factors = self.validate_positive_int(options["factors"], "--factors")
        iterations = self.validate_positive_int(
            options["iterations"],
            "--iterations",
        )
        max_features = self.validate_positive_int(
            options["max_features"],
            "--max-features",
        )
        regularization = self.validate_positive_float(
            options["regularization"],
            "--regularization",
        )

        als_threads, als_thread_source = self.resolve_als_threads(
            options["als_threads"]
        )

        artifact_dir = self.get_artifact_dir()
        artifact_dir.mkdir(parents=True, exist_ok=True)

        products = list(
            self.get_live_products_queryset()
            .select_related("producer", "category", "product_type")
            .order_by("id")
        )

        if not products:
            self.stdout.write(self.style.ERROR("No live products found."))
            return

        product_id_to_idx, idx_to_product_id = self.build_product_indexes(products)

        tfidf_vectorizer, tfidf_matrix = self.build_tfidf_matrix(
            products=products,
            max_features=max_features,
        )

        interaction_rows = self.collect_interactions(product_id_to_idx)

        (
            user_id_to_idx,
            user_item_matrix,
            als_user_factors,
            als_item_factors,
            als_available,
        ) = self.build_als_outputs(
            interaction_rows=interaction_rows,
            product_id_to_idx=product_id_to_idx,
            product_count=len(products),
            factors=factors,
            iterations=iterations,
            regularization=regularization,
            als_threads=als_threads,
        )

        self.save_artifacts(
            artifact_dir=artifact_dir,
            tfidf_matrix=tfidf_matrix,
            user_item_matrix=user_item_matrix,
            als_user_factors=als_user_factors,
            als_item_factors=als_item_factors,
            tfidf_vectorizer=tfidf_vectorizer,
            user_id_to_idx=user_id_to_idx,
            product_id_to_idx=product_id_to_idx,
            idx_to_product_id=idx_to_product_id,
        )

        metadata = {
            "trained_at": timezone.now().isoformat(),
            "product_count": len(products),
            "interaction_count": len(interaction_rows),
            "user_count": len(user_id_to_idx),
            "als_available": als_available,
            "factors": factors,
            "iterations": iterations,
            "regularization": regularization,
            "als_threads": als_threads,
            "als_thread_source": als_thread_source,
            "cpu_count": os.cpu_count() or 1,
            "max_tfidf_features": max_features,
            "openblas_threads": os.environ.get("OPENBLAS_NUM_THREADS", "1"),
            "omp_threads": os.environ.get("OMP_NUM_THREADS", "1"),
            "mkl_threads": os.environ.get("MKL_NUM_THREADS", "1"),
            "numexpr_threads": os.environ.get("NUMEXPR_NUM_THREADS", "1"),
        }

        self.save_metadata(artifact_dir, metadata)
        self.print_summary(metadata, artifact_dir)

    def get_artifact_dir(self):
        return Path(settings.BASE_DIR) / "ai_recommendations" / "artifacts"

    def validate_positive_int(self, value, option_name):
        if value is None or value < 1:
            raise CommandError(f"{option_name} must be a positive integer.")

        return value

    def validate_positive_float(self, value, option_name):
        if value is None or value <= 0:
            raise CommandError(f"{option_name} must be greater than 0.")

        return value

    def resolve_als_threads(self, cli_value):
        """
        Resolve ALS thread count in this priority order:

        1. Command argument: --als-threads 2
        2. Environment variable: RECOMMENDER_ALS_THREADS=2
        3. Conservative automatic rule
        """
        if cli_value is not None:
            if cli_value < 1:
                raise CommandError("--als-threads must be a positive integer.")

            return cli_value, "command_argument"

        env_value = os.environ.get("RECOMMENDER_ALS_THREADS")

        if env_value:
            try:
                env_threads = int(env_value)
            except ValueError:
                self.stdout.write(
                    self.style.WARNING(
                        "Invalid RECOMMENDER_ALS_THREADS value. "
                        "Using automatic ALS thread selection."
                    )
                )
            else:
                if env_threads >= 1:
                    return env_threads, "environment"

                self.stdout.write(
                    self.style.WARNING(
                        "RECOMMENDER_ALS_THREADS must be at least 1. "
                        "Using automatic ALS thread selection."
                    )
                )

        cpu_count = os.cpu_count() or 1
        return choose_default_als_threads(cpu_count), "automatic"

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

    def build_product_indexes(self, products):
        product_id_to_idx = {
            product.id: index for index, product in enumerate(products)
        }
        idx_to_product_id = {
            index: product_id for product_id, index in product_id_to_idx.items()
        }

        return product_id_to_idx, idx_to_product_id

    def build_tfidf_matrix(self, products, max_features):
        product_texts = [self.build_product_text(product) for product in products]

        tfidf_vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 2),
            stop_words="english",
        )
        tfidf_matrix = tfidf_vectorizer.fit_transform(product_texts)

        return tfidf_vectorizer, tfidf_matrix

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

        return " ".join(str(part).strip() for part in parts if part).strip()

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

    def build_als_outputs(
        self,
        interaction_rows,
        product_id_to_idx,
        product_count,
        factors,
        iterations,
        regularization,
        als_threads,
    ):
        if not interaction_rows:
            self.stdout.write(
                self.style.WARNING(
                    "No logged-in interactions or completed orders found. "
                    "TF-IDF was trained, but ALS could not be trained."
                )
            )

            return (
                {},
                sparse.csr_matrix((0, product_count), dtype=np.float32),
                np.zeros((0, factors), dtype=np.float32),
                np.zeros((product_count, factors), dtype=np.float32),
                False,
            )

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
            shape=(len(user_ids), product_count),
            dtype=np.float32,
        )
        user_item_matrix.sum_duplicates()

        als_model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            iterations=iterations,
            random_state=DEFAULT_RANDOM_STATE,
            num_threads=als_threads,
        )

        als_model.fit(user_item_matrix, show_progress=False)

        return (
            user_id_to_idx,
            user_item_matrix,
            als_model.user_factors,
            als_model.item_factors,
            True,
        )

    def save_artifacts(
        self,
        artifact_dir,
        tfidf_matrix,
        user_item_matrix,
        als_user_factors,
        als_item_factors,
        tfidf_vectorizer,
        user_id_to_idx,
        product_id_to_idx,
        idx_to_product_id,
    ):
        sparse.save_npz(artifact_dir / "tfidf_matrix.npz", tfidf_matrix)
        sparse.save_npz(artifact_dir / "user_item_matrix.npz", user_item_matrix)

        np.save(artifact_dir / "als_user_factors.npy", als_user_factors)
        np.save(artifact_dir / "als_item_factors.npy", als_item_factors)

        joblib.dump(tfidf_vectorizer, artifact_dir / "tfidf_vectorizer.joblib")
        joblib.dump(user_id_to_idx, artifact_dir / "user_id_to_idx.joblib")
        joblib.dump(product_id_to_idx, artifact_dir / "product_id_to_idx.joblib")
        joblib.dump(idx_to_product_id, artifact_dir / "idx_to_product_id.joblib")

    def save_metadata(self, artifact_dir, metadata):
        with open(artifact_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def print_summary(self, metadata, artifact_dir):
        self.stdout.write(
            self.style.SUCCESS("AI recommender trained from Django database.")
        )
        self.stdout.write(f"Products:       {metadata['product_count']}")
        self.stdout.write(f"Users:          {metadata['user_count']}")
        self.stdout.write(f"Interactions:   {metadata['interaction_count']}")
        self.stdout.write(f"ALS available:  {metadata['als_available']}")
        self.stdout.write(f"ALS threads:    {metadata['als_threads']}")
        self.stdout.write(f"Thread source:  {metadata['als_thread_source']}")
        self.stdout.write(f"CPU count:      {metadata['cpu_count']}")
        self.stdout.write(f"Artefacts:      {artifact_dir}")