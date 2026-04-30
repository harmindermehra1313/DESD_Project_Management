#!/bin/sh
set -e

echo "Running migrations before recommender training..."
python manage.py migrate --noinput

if [ "$FORCE_RETRAIN_RECOMMENDER" = "1" ] || [ ! -f "ai_recommendations/artifacts/metadata.json" ]; then
  echo "Training recommender..."
  python manage.py train_ai_recommender_from_db
else
  echo "Recommender artefacts already exist. Skipping training."
fi