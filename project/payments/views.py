from django.shortcuts import render
import stripe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .webhook_handlers import handle_payment_intent_succeeded
import logging
logger = logging.getLogger(__name__)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.exception("Webhook signature verification failed: %s", e)
        return HttpResponse(status=400)

    logger.debug("Received Stripe event: %s", event["type"])

    try:
        if event["type"] == "payment_intent.succeeded":
            logger.debug("Handling payment_intent.succeeded for %s", event["data"]["object"]["id"])
            handle_payment_intent_succeeded(event)
    except Exception as e:
        logger.exception("Webhook handler crashed: %s", e)
        return HttpResponse(status=500)

    return HttpResponse(status=200)

# Create your views here.
def index(request):
    return render(request, "payments/index.html")