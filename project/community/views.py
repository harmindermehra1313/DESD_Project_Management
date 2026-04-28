from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from BRFN.decorators import admin_required, producer_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from django.urls import reverse
from .models import Recipe, FarmStory, RecipeProduct
from .forms import RecipeForm, FarmStoryForm
from accounts.models import Producer
from products.models import Product


def index(request):
    return render(request, "community/index.html")


def contact_us(request):
    context = {
        "contact_phone": "0800 00 1066",
        "contact_email": "BRFN@farmers.co.uk",
        "contact_address": "Coldharbour Lane, Bristol, BS16 1QY",
    }
    return render(request, "community/contact_us.html", context)