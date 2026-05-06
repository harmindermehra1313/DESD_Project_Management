from django.db import models
from django.conf import settings
from django.utils import timezone


class AIUsage(models.Model):

    class ModelType(models.TextChoices):
        RECOMMENDER = "REC", "Recommender System"
        CLASSIFIER = "CLS", "Fruit/Veg Classifier"

    class Component(models.TextChoices):
        TFIDF = "TFIDF", "TF-IDF"
        ALS = "ALS", "ALS Matrix Factorisation"
        HYBRID = "HYB", "Hybrid (TF-IDF + ALS)"
        CLASSIFIER = "ABC", "ABC Classifier"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_logs"
    )

    model_type = models.CharField(max_length=5, choices=ModelType.choices)
    component = models.CharField(max_length=10, choices=Component.choices)

    model_version = models.CharField(max_length=50, null=True, blank=True)

    input_data = models.JSONField(null=True, blank=True)
    output_data = models.JSONField(null=True, blank=True)

    execution_time_ms = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_model_type_display()} ({self.model_version}) @ {self.created_at:%Y-%m-%d %H:%M}"


class ClassifierModel(models.Model):
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    file = models.FileField(upload_to="classifier_models/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_active:
            ClassifierModel.objects.update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (v{self.version}){' [ACTIVE]' if self.is_active else ''}"
