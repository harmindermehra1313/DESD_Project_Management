import time
from .models import AIUsage, ClassifierModel


class AITracker:

    @staticmethod
    def log_recommender(user, component, input_data, output_data, start_time, version="v1"):
        AIUsage.objects.create(
            user=user,
            model_type=AIUsage.ModelType.RECOMMENDER,
            component=component,
            model_version=version,
            input_data=input_data,
            output_data=output_data,
            execution_time_ms=(time.time() - start_time) * 1000
        )

    @staticmethod
    def log_classifier(user, input_data, output_data, start_time, version):
        AIUsage.objects.create(
            user=user,
            model_type=AIUsage.ModelType.CLASSIFIER,
            component=AIUsage.Component.CLASSIFIER,
            model_version=version,
            input_data=input_data,
            output_data=output_data,
            execution_time_ms=(time.time() - start_time) * 1000
        )


def load_active_classifier():
    model_obj = ClassifierModel.objects.filter(is_active=True).first()
    if not model_obj:
        raise RuntimeError("No active classifier model found.")
    return model_obj.file.path, model_obj.version
