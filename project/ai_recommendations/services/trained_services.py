from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import time
from django.conf import settings
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity

from products.models import Product
from .services import get_live_products_queryset
from ai_admin.services import AITracker
from django.contrib.auth import get_user_model
User = get_user_model()

@dataclass(frozen=True)
class TrainedRecommendationResult:
    product: Product
    score: float
    reason: str
    signals: dict



def load_artifacts():
    artifact_dir = Path(settings.BASE_DIR) / "ai_recommendations" / "artifacts"

    required = [
        "tfidf_matrix.npz",
        "user_item_matrix.npz",
        "als_user_factors.npy",
        "als_item_factors.npy",
        "user_id_to_idx.joblib",
        "product_id_to_idx.joblib",
        "idx_to_product_id.joblib",
        "metadata.json",
    ]

    missing = [
        filename for filename in required if not (artifact_dir / filename).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing trained recommender artefacts: " + ", ".join(missing)
        )

    return {
        "tfidf_matrix": sparse.load_npz(artifact_dir / "tfidf_matrix.npz"),
        "user_item_matrix": sparse.load_npz(artifact_dir / "user_item_matrix.npz"),
        "als_user_factors": np.load(artifact_dir / "als_user_factors.npy"),
        "als_item_factors": np.load(artifact_dir / "als_item_factors.npy"),
        "user_id_to_idx": joblib.load(artifact_dir / "user_id_to_idx.joblib"),
        "product_id_to_idx": joblib.load(artifact_dir / "product_id_to_idx.joblib"),
        "idx_to_product_id": joblib.load(artifact_dir / "idx_to_product_id.joblib"),
    }


def clear_artifact_cache():
    pass


def get_trained_recommendations_for_request(
    request,
    current_product=None,
    limit=4,
):
    if not request.user.is_authenticated:
        return []

    return get_trained_recommendations(
        user_id=request.user.id,
        current_product=current_product,
        limit=limit,
    )


def get_trained_recommendations(user_id, current_product=None, limit=4):
    start = time.time()
    artifacts = load_artifacts()

    tfidf_matrix = artifacts["tfidf_matrix"]
    user_item_matrix = artifacts["user_item_matrix"]
    als_user_factors = artifacts["als_user_factors"]
    als_item_factors = artifacts["als_item_factors"]
    user_id_to_idx = artifacts["user_id_to_idx"]
    product_id_to_idx = artifacts["product_id_to_idx"]
    idx_to_product_id = artifacts["idx_to_product_id"]

    user_idx = user_id_to_idx.get(user_id)
    current_item_idx = None

    if current_product is not None:
        current_item_idx = product_id_to_idx.get(current_product.id)

    if user_idx is not None and user_idx < user_item_matrix.shape[0]:
        als_scores = als_item_factors @ als_user_factors[user_idx]
        tfidf_scores = build_user_tfidf_scores(
            user_idx=user_idx,
            user_item_matrix=user_item_matrix,
            tfidf_matrix=tfidf_matrix,
        )
        seen_indices = set(user_item_matrix[user_idx].indices)
        alpha = 0.7
    else:
        als_scores = np.zeros(tfidf_matrix.shape[0])
        tfidf_scores = build_current_product_tfidf_scores(
            current_item_idx=current_item_idx,
            tfidf_matrix=tfidf_matrix,
        )
        seen_indices = set()
        alpha = 0.0

    als_scores_norm = normalise(als_scores)
    tfidf_scores_norm = normalise(tfidf_scores)

    hybrid_scores = alpha * als_scores_norm + (1 - alpha) * tfidf_scores_norm

    live_products = {
        product.id: product
        for product in get_live_products_queryset().select_related(
            "producer", "category", "product_type"
        )
    }

    results = []

    for item_idx, score in enumerate(hybrid_scores):
        product_id = idx_to_product_id.get(item_idx)
        product = live_products.get(product_id)

        if product is None:
            continue

        if current_product is not None and product.id == current_product.id:
            continue

        als_signal = float(als_scores_norm[item_idx])
        tfidf_signal = float(tfidf_scores_norm[item_idx])
        hybrid_signal = float(score)

        signals = {
            "als": round(als_signal, 3),
            "tfidf": round(tfidf_signal, 3),
            "hybrid": round(hybrid_signal, 3),
        }

        results.append(
            TrainedRecommendationResult(
                product=product,
                score=round(hybrid_signal, 3),
                reason=build_reason(
                    signals=signals,
                    user_idx=user_idx,
                    product=product,
                    current_product=current_product,
                ),
                signals=signals,
            )
        )

    results.sort(key=lambda result: result.score, reverse=True)

    # Determine which component was used
    if alpha == 0.0:
        component_used = "TFIDF"
    elif alpha == 0.7:
        component_used = "HYB"
    else:
        component_used = "ALS"

    # Log AI usage
    user_obj = User.objects.filter(id=user_id).first()
    AITracker.log_recommender(
        user=user_obj,
        component=component_used,
        input_data={
            "user_id": user_id,
            "current_product": current_product.id if current_product else None,
        },
        output_data={
            "recommendation_count": len(results[:limit])
        },
        start_time=start,
        version="v1"
    )

    if len(results) < limit:
        existing_product_ids = {result.product.id for result in results}

        fallback_products = (
            get_live_products_queryset()
            .select_related("producer", "category", "product_type")
            .exclude(id__in=existing_product_ids)
            .order_by("-created_at")
        )

        if current_product is not None:
            fallback_products = fallback_products.exclude(id=current_product.id)

        for product in fallback_products[: limit - len(results)]:
            results.append(
                TrainedRecommendationResult(
                    product=product,
                    score=0.001,
                    reason=(
                        "Available product added while recommendation " "history grows."
                    ),
                    signals={
                        "als": 0.0,
                        "tfidf": 0.0,
                        "hybrid": 0.001,
                    },
                )
            )

    return results[:limit]


def build_user_tfidf_scores(user_idx, user_item_matrix, tfidf_matrix):
    user_row = user_item_matrix[user_idx]
    interacted_indices = user_row.indices

    if len(interacted_indices) == 0:
        return np.zeros(tfidf_matrix.shape[0])

    profile = tfidf_matrix[interacted_indices].mean(axis=0)
    profile = np.asarray(profile).reshape(1, -1)

    return cosine_similarity(profile, tfidf_matrix).ravel()


def build_current_product_tfidf_scores(current_item_idx, tfidf_matrix):
    if current_item_idx is None:
        return np.zeros(tfidf_matrix.shape[0])

    current_vector = tfidf_matrix[current_item_idx]
    return cosine_similarity(current_vector, tfidf_matrix).ravel()


def normalise(scores):
    scores = np.asarray(scores, dtype="float64")

    if scores.size == 0:
        return scores

    score_min = scores.min()
    score_max = scores.max()

    if score_max == score_min:
        return np.zeros_like(scores)

    return (scores - score_min) / (score_max - score_min)


def build_reason(signals, user_idx, product=None, current_product=None):
    """
    Return a clear customer-facing explanation for the recommendation.
    """
    if current_product is not None and product is not None:
        if (
            current_product.product_type_id
            and product.product_type_id
            and product.product_type_id == current_product.product_type_id
        ):
            return "Recommended as a close match to this product."

        if (
            current_product.category_id
            and product.category_id == current_product.category_id
        ):
            return "Recommended from the same product category."

    if user_idx is None:
        return "Recommended based on product similarity."

    return "Recommended based on previous customer activity."