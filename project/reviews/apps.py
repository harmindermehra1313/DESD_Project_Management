import os
from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return
        from reviews.services.moderation_service import get_model
        
        

        # get_model()