from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import AnonymousUser
from PIL import Image

import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T

from torchvision.models.efficientnet import MBConv

from ai_admin.services import AITracker, load_active_classifier
import time

def _patched_mbconv_forward(self, input: torch.Tensor) -> torch.Tensor:
    result = self.block(input)
    if self.use_res_connect:
        result = self.stochastic_depth(result)
        result = result + input 
    return result

MBConv.forward = _patched_mbconv_forward

if hasattr(models.efficientnet, 'FusedMBConv'):
    from torchvision.models.efficientnet import FusedMBConv
    def _patched_fused_forward(self, input: torch.Tensor) -> torch.Tensor:
        result = self.block(input)
        if self.use_res_connect:
            result = self.stochastic_depth(result)
            result = result + input
        return result
    FusedMBConv.forward = _patched_fused_forward

# Configure matplotlib backend early to prevent runtime issues
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

CLASS_LABELS = ["Fresh", "Borderline", "Spoiled"]
CLASS_COLOURS = ["#22c55e", "#f59e0b", "#ef4444"]   # green / amber / red

IMG_SIZE = 224          # resize target for the model
GRAD_CAM_LAYER = "features.8"  # last conv layer name (EfficientNet default)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff", "image/gif"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB

FRESHNESS_RECOMMENDATIONS = {
    "Fresh": (
        "This produce looks fresh and in excellent condition. "
        "It is ready for sale or immediate use. Store appropriately "
        "to maintain quality."
    ),
    "Borderline": (
        "This produce shows early signs of deterioration. Consider "
        "marking it for a surplus reduction, using it promptly, or "
        "inspecting it more closely before listing."
    ),
    "Spoiled": (
        "This produce appears spoiled and should not be listed for sale. "
        "Remove it from stock, check neighbouring inventory for "
        "cross-contamination, and dispose of it safely."
    ),
}

# ─────────────────────────────────────────────────────────────
# Model Loading (thread-safe singleton)
# ─────────────────────────────────────────────────────────────

_model: Optional[nn.Module] = None
_model_lock = threading.Lock()
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model(model_path: str) -> nn.Module:
    """
    Load the PyTorch freshness model once and cache it.

    The loader attempts (in order):
      1. torch.load() with weights_only=False  — works for full state_dict
         or TorchScript models saved with torch.save(model, ...)
      2. If the loaded object is a state_dict (OrderedDict), it builds a
         ResNet-50 backbone, replaces the final FC layer with a 3-class
         head, and loads the weights.

    Override this function if your architecture differs.
    """
    global _model

    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:          # double-checked locking
            return _model

        #model_path = getattr(settings, "FRESHNESS_MODEL_PATH", None)
        if not model_path or not Path(model_path).exists():
            raise FileNotFoundError(
                "Freshness model not found. Set FRESHNESS_MODEL_PATH in settings.py "
                f"(looked for: {model_path})"
            )

        checkpoint = torch.load(model_path, map_location=_device, weights_only=False)

        # Case 1: full model object
        if isinstance(checkpoint, nn.Module):
            net = checkpoint

        # Case 2: state dict — build EfficientNet-B0 with 3-class head
        elif isinstance(checkpoint, dict):
            net = models.efficientnet_b0(weights=None)
            net.classifier[1] = nn.Linear(net.classifier[1].in_features, len(CLASS_LABELS))
            
            # Handle both raw state dicts and wrapper dicts
            state = (
                checkpoint.get("state_dict")
                or checkpoint.get("model_state_dict")
                or checkpoint
            )
            net.load_state_dict(state, strict=True)

        else:
            raise TypeError(f"Unrecognised model checkpoint type: {type(checkpoint)}")

        net.to(_device)
        net.eval()

        def replace_inplace(model_layer):
            for name, child in model_layer.named_children():
                if isinstance(child, nn.SiLU):
                    setattr(model_layer, name, nn.SiLU(inplace=False))
                elif isinstance(child, nn.ReLU):
                    setattr(model_layer, name, nn.ReLU(inplace=False))
                else:
                    replace_inplace(child)
                    
        replace_inplace(net)

        _model = net
        logger.info("Freshness model loaded from %s on %s", model_path, _device)
        return _model

# ─────────────────────────────────────────────────────────────
# Image Pre-processing
# ─────────────────────────────────────────────────────────────

_transform = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.ToTensor(),
])

def _pil_to_tensor(pil_img: Image.Image) -> torch.Tensor:
    """Return a normalised (1, 3, H, W) tensor with gradient tracking."""
    t = _transform(pil_img).unsqueeze(0).to(_device)
    t.requires_grad_(True)
    return t


def _tensor_to_b64(t: torch.Tensor) -> str:
    """Convert a (H, W, 3) uint8 numpy array or similar tensor to base64 PNG."""
    arr = t.detach().cpu().numpy()
    if arr.max() <= 1.0:
        arr = (arr * 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _overlay_heatmap(heatmap: np.ndarray, base_img: Image.Image, alpha: float = 0.5) -> str:
    """Blend a (H, W) float heatmap [0,1] with the original image; return base64 PNG."""
    h, w = np.array(base_img).shape[:2]
    heatmap_resized = np.array(
        Image.fromarray((heatmap * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    ) / 255.0

    coloured = cm.jet(heatmap_resized)[..., :3]   # (H, W, 3) RGB float
    base_arr = np.array(base_img.convert("RGB").resize((w, h))) / 255.0
    blended = alpha * coloured + (1 - alpha) * base_arr
    blended = np.clip(blended * 255, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(blended).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _attr_to_b64(attr: np.ndarray, base_img: Image.Image) -> str:
    """Turn a (H, W) or (H, W, 3) attribution map into an overlaid base64 PNG."""
    if attr.ndim == 3:
        attr = attr.mean(axis=-1)
    attr = attr - attr.min()
    denom = attr.max()
    if denom > 1e-8:
        attr /= denom
    return _overlay_heatmap(attr, base_img)


# ─────────────────────────────────────────────────────────────
# Explainability Methods
# ─────────────────────────────────────────────────────────────

def _run_grad_cam(model: nn.Module, tensor: torch.Tensor, class_idx: int,
                  base_img: Image.Image) -> str:
    """Grad-CAM using the layer named GRAD_CAM_LAYER."""
    activations, gradients = [], []

    def forward_hook(_, __, output):
        activations.append(output)

    def backward_hook(_, __, grad_output):
        gradients.append(grad_output[0])

    layer = dict(model.named_modules()).get(GRAD_CAM_LAYER)
    if layer is None:
        # Try to find the last Conv2d automatically
        for name, mod in model.named_modules():
            if isinstance(mod, nn.Conv2d):
                layer_name = name
        layer = dict(model.named_modules())[layer_name]

    fh = layer.register_forward_hook(forward_hook)
    bh = layer.register_full_backward_hook(backward_hook)

    try:
        output = model(tensor)
        model.zero_grad()
        output[0, class_idx].backward()
    finally:
        fh.remove()
        bh.remove()

    act = activations[0].detach().cpu().numpy()[0]   # (C, H, W)
    grad = gradients[0].detach().cpu().numpy()[0]     # (C, H, W)

    weights = grad.mean(axis=(1, 2))                  # (C,)
    cam = np.maximum((weights[:, None, None] * act).sum(axis=0), 0)
    cam = cam - cam.min()
    if cam.max() > 1e-8:
        cam /= cam.max()

    return _overlay_heatmap(cam, base_img)


def _run_integrated_gradients(model: nn.Module, tensor: torch.Tensor,
                               class_idx: int, base_img: Image.Image,
                               steps: int = 50) -> str:
    """Integrated Gradients via Captum if available, else manual implementation."""
    try:
        from captum.attr import IntegratedGradients
        ig = IntegratedGradients(model)
        baseline = torch.zeros_like(tensor).to(_device)
        attr = ig.attribute(tensor, baseline, target=class_idx, n_steps=steps)
        attr_np = attr.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
    except ImportError:
        # Manual IG fallback
        baseline = torch.zeros_like(tensor)
        integrated = torch.zeros_like(tensor)
        for k in range(1, steps + 1):
            alpha = k / steps
            interp = baseline + alpha * (tensor - baseline)
            interp = interp.clone().detach().requires_grad_(True)
            out = model(interp)
            model.zero_grad()
            out[0, class_idx].backward()
            integrated += interp.grad.detach()
        attr = (tensor - baseline) * integrated / steps
        attr_np = attr.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()

    return _attr_to_b64(attr_np, base_img)


def _run_lime(model: nn.Module, pil_img: Image.Image, class_idx: int) -> str:
    """LIME superpixel explanation."""
    try:
        from lime import lime_image
        from skimage.segmentation import mark_boundaries
    except ImportError:
        return _placeholder_b64(pil_img, "LIME not installed.\npip install lime")

    img_arr = np.array(pil_img.resize((IMG_SIZE, IMG_SIZE)))

    def batch_predict(images):
        model.eval()
        preds = []
        for img in images:
            pil = Image.fromarray(img.astype(np.uint8))
            t = _transform(pil).unsqueeze(0).to(_device)
            with torch.no_grad():
                out = torch.softmax(model(t), dim=1)
            preds.append(out.squeeze(0).cpu().numpy())
        return np.array(preds)

    explainer = lime_image.LimeImageExplainer()
    explanation = explainer.explain_instance(
        img_arr,
        batch_predict,
        top_labels=len(CLASS_LABELS),
        hide_color=0,
        num_samples=300,
    )
    temp, mask = explanation.get_image_and_mask(
        class_idx, positive_only=True, num_features=10, hide_rest=True
    )
    lime_img = mark_boundaries(temp / 255.0, mask)
    lime_img = np.clip(lime_img * 255, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(lime_img).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _run_shap(model: nn.Module, tensor: torch.Tensor,
              class_idx: int, base_img: Image.Image) -> str:
    """GradientSHAP via Captum, optimized for fast web inference."""
    try:
        from captum.attr import GradientShap
    except ImportError:
        return _placeholder_b64(base_img, "Captum not installed.")

    # Create a fast, lightweight baseline for the web (black and white frames)
    baselines = torch.cat([
        torch.zeros_like(tensor), 
        torch.ones_like(tensor)
    ], dim=0).to(_device)

    explainer = GradientShap(model)
    
    try:
        # Keep n_samples relatively low (e.g., 10) so the web request doesn't timeout
        attributions = explainer.attribute(
            tensor,
            baselines=baselines,
            target=class_idx,
            n_samples=10,  
            stdevs=0.1
        )
        
        
        attr_np = attributions.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
        return _attr_to_b64(attr_np, base_img)
        
    except Exception as e:
        logger.error("Captum SHAP failed: %s", e, exc_info=True)
        return _placeholder_b64(base_img, f"SHAP error:\n{e}")


def _placeholder_b64(base_img: Image.Image, message: str) -> str:
    """Return a greyed-out image with a message when a library is unavailable."""
    fig, ax = plt.subplots(figsize=(3, 3))
    arr = np.array(base_img.resize((IMG_SIZE, IMG_SIZE))).astype(float) / 255.0
    ax.imshow(arr, alpha=0.3)
    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            ha="center", va="center", fontsize=9, color="red",
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", bbox_inches="tight", dpi=80)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────────────────────
# Django Views
# ─────────────────────────────────────────────────────────────

def freshness_check_page(request):
    """Renders the freshness check UI page."""
    return render(request, "products/freshness_check.html")


@require_http_methods(["POST"])
@csrf_exempt
def freshness_check_api(request):
    """
    POST /products/freshness/analyse/
    Accepts: multipart/form-data with field 'image'
    Returns: JSON with scores, label, recommendation, and 4 base64 explainability images.
    """
    start_time = time.time()
    # ── Validate upload ──────────────────────────────────────
    uploaded = request.FILES.get("image")
    if not uploaded:
        return JsonResponse({"error": "No image uploaded."}, status=400)

    if uploaded.size > MAX_UPLOAD_BYTES:
        return JsonResponse({"error": "Image must be under 10 MB."}, status=400)

    content_type = uploaded.content_type or ""
    if content_type not in ALLOWED_MIME:
        return JsonResponse(
            {"error": f"Unsupported file type '{content_type}'. Upload a JPEG, PNG, or WebP."}, status=400
        )

    try:
        pil_img = Image.open(uploaded).convert("RGB")
    except Exception:
        return JsonResponse({"error": "Could not read the uploaded image."}, status=400)

    # ── Load model ───────────────────────────────────────────
    try:
        model_path, model_version = load_active_classifier()
        model = _load_model(model_path)
    except FileNotFoundError as exc:
        logger.error("Model not found: %s", exc, exc_info=True)
        return JsonResponse({"error": str(exc)}, status=503)
    except Exception as exc:
        logger.exception("Failed to load freshness model")
        return JsonResponse({"error": f"Model load error: {exc}"}, status=503)

    # ── Inference ────────────────────────────────────────────
    tensor = _pil_to_tensor(pil_img)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

    class_idx = int(probs.argmax())
    label = CLASS_LABELS[class_idx]
    freshness_pct = float(probs[0]) * 100           # "Fresh" probability as freshness score

    scores = [
        {"label": CLASS_LABELS[i], "score": round(float(probs[i]) * 100, 1), "colour": CLASS_COLOURS[i]}
        for i in range(len(CLASS_LABELS))
    ]

    # ── Explainability (re-enable grad for CAM / IG) ─────────
    tensor_grad = _pil_to_tensor(pil_img)   # fresh tensor with grad

    try:
        grad_cam_b64 = _run_grad_cam(model, tensor_grad, class_idx, pil_img)
    except Exception as exc:
        logger.error("Grad-CAM failed: %s", exc, exc_info=True)
        grad_cam_b64 = _placeholder_b64(pil_img, f"Grad-CAM error:\n{exc}")

    try:
        ig_b64 = _run_integrated_gradients(model, tensor_grad, class_idx, pil_img)
    except Exception as exc:
        logger.error("Integrated Gradients failed: %s", exc, exc_info=True)
        ig_b64 = _placeholder_b64(pil_img, f"IG error:\n{exc}")

    try:
        lime_b64 = _run_lime(model, pil_img, class_idx)
    except Exception as exc:
        logger.error("LIME failed: %s", exc, exc_info=True)
        lime_b64 = _placeholder_b64(pil_img, f"LIME error:\n{exc}")

    try:
        shap_b64 = _run_shap(model, tensor_grad, class_idx, pil_img)
    except Exception as exc:
        logger.error("SHAP failed: %s", exc, exc_info=True)
        shap_b64 = _placeholder_b64(pil_img, f"SHAP error:\n{exc}")

    # AI Usage Logging
    try:
        AITracker.log_classifier(
            user=request.user if request.user.is_authenticated else None,
            input_data={
                "filename": uploaded.name,
                "content_type": uploaded.content_type,
                "size_bytes": uploaded.size,
            },
            output_data={
                "label": label,
                "scores": scores,
                "freshness_pct": freshness_pct,
            },
            start_time=start_time,
            version=model_version,
        )
    except Exception as exc:
        logger.error("Failed to log classifier usage: %s", exc, exc_info=True)

    return JsonResponse({
        "label": label,
        "freshness_pct": round(freshness_pct, 1),
        "scores": scores,
        "recommendation": FRESHNESS_RECOMMENDATIONS[label],
        "explainability": {
            "grad_cam":              {"title": "Grad-CAM",               "image": grad_cam_b64},
            "integrated_gradients":  {"title": "Integrated Gradients",   "image": ig_b64},
            "lime":                  {"title": "LIME",                    "image": lime_b64},
            "shap":                  {"title": "SHAP",                   "image": shap_b64},
        },
    })
