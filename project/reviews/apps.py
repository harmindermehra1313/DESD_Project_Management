import logging
import os
import sys
from threading import Lock

from django.apps import AppConfig

logger = logging.getLogger(__name__)

_model_preload_lock = Lock()
_model_preloaded = False


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"

    def ready(self):
        global _model_preloaded

        if os.environ.get("PRELOAD_REVIEW_MODERATION") != "1":
            return

        if "runserver" not in sys.argv:
            return

        if os.environ.get("RUN_MAIN") != "true":
            return

        if _model_preloaded:
            return

        with _model_preload_lock:
            if _model_preloaded:
                return

            from reviews.services.moderation_service import get_model

            get_model()
            _model_preloaded = True
            logger.info("Review moderation model preloaded successfully.")