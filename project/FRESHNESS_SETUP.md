# Freshness Checker Setup Guide

## Model File Location

Place your trained PyTorch freshness model at:

```
project/ml_models/model_AtoC.pt
```

**Full absolute path:**
```
C:\Users\joeth\Documents\GROUPWORK2\Desd_groupwork\project\ml_models\model_AtoC.pt
```

Create the `ml_models/` directory if it doesn't exist:
```bash
mkdir project/ml_models
```

## Django Settings Configuration

Add the following to your `BRFN/settings.py`:

```python
# Freshness Checker Model Path
FRESHNESS_MODEL_PATH = BASE_DIR / "ml_models" / "model_AtoC.pt"

# Optional: Enable/disable the freshness API (defaults to True in production)
FOOD_MILES_ENABLE_API = True
```

## Model Requirements

The model should be compatible with one of these formats:

1. **TorchScript Model** — Full model saved with `torch.save(model, path)`
2. **State Dict** — Just the weights, saved with `torch.save(model.state_dict(), path)`
   - Will auto-build ResNet-50 with 3-class output head
   - Classes: Fresh, Borderline, Spoiled

## Dependencies

Install required packages:

```bash
pip install torch torchvision
pip install captum  # For Integrated Gradients
pip install lime    # For LIME explanations
pip install shap    # For SHAP explanations
```

## Page Access

- **URL**: `/products/freshness/`
- **API Endpoint**: `POST /products/freshness/analyse/`
- **Restricted to**: Producers (can be customized in `freshness_check.py`)

## Optional: Restrict Access

To limit freshness checker to authenticated producers only:

Edit `project/products/views/freshness_check.py` and uncomment:

```python
@login_required(login_url="/accounts/login/")
def freshness_check_page(request):
    # ... rest of code
```

## Troubleshooting

If you see "Model not found" error:
1. Verify the file exists at `project/ml_models/model_AtoC.pt`
2. Check that `FRESHNESS_MODEL_PATH` is correctly set in settings.py
3. Ensure the file is a valid PyTorch model (try `torch.load()` in Python shell)

If explainability methods fail:
- They'll show a greyed-out placeholder image with the error
- Install the missing library (captum, lime, shap) as needed
- Inference and main recommendations will still work

## Model Input/Output

**Input:**
- Images: 224x224 RGB tensors
- Normalized with ImageNet means/stds

**Output:**
- Class probabilities for: Fresh, Borderline, Spoiled
- Recommendation text based on classification
- AI attribution maps (Grad-CAM, IG, LIME, SHAP)
