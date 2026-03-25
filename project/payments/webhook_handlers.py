from orders.services.order_creation import create_order_from_session
from payments.models import Payment
from orders.models import Order
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from orders.services.session_loader import load_checkout_data_from_session
from orders.services.order_validation import validate_checkout_session
import logging
from .stripe_client import get_stripe

logger = logging.getLogger(__name__)
User = get_user_model()
stripe = get_stripe()

class FakeRequest:
    """
    Minimal request-like object so create_order_from_session()
    can access .session and .user.
    """
    def __init__(self, session_key, user):
        self.session = SessionStore(session_key=session_key)
        self.user = user

def build_request_from_session(session_key: str, user_id: str | None):
    """
    Reconstructs a minimal request-like object for the order creation service.
    """
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    return FakeRequest(session_key=session_key, user=user)

def handle_payment_intent_succeeded(event):
    """
    Called by webhook router when Stripe sends payment_intent.succeeded.
    Creates the order AFTER payment succeeds.
    """
    try:
        intent = event["data"]["object"]
        metadata = intent.get("metadata", {})

        session_key = metadata.get("session_key")
        user_id = metadata.get("user_id")

        if not session_key:
            raise ValueError("Missing session_key in PaymentIntent metadata.")

        # Load checkout data from session
        checkout_data = load_checkout_data_from_session(session_key)

        # Validate using same serializer as COD
        validated_data = validate_checkout_session(checkout_data)

        # Build fake request-like object
        request = build_request_from_session(session_key, user_id)

        # Create order using reusable service
        order = create_order_from_session(
            request=request,
            validated_data=validated_data,
            payment_method="CRD",
            payment_intent_id=intent["id"],
        )

        # Update PaymentIntent with real order id
        stripe.PaymentIntent.modify(
            intent["id"],
            metadata={
                "order_id": order.id,
                "session_key": session_key,
                "user_id": user_id or "",
            }
        )
        # Retrieve fresh Stripe data with expanded relations
        payment_intent = stripe.PaymentIntent.retrieve(
            intent["id"],
            expand=["latest_charge", "payment_method"],
        )
        card_brand = None
        card_last4 = None
        payment_method = payment_intent.get("payment_method")
        if isinstance(payment_method, dict):
            card = payment_method.get("card") or {}
            card_brand = card.get("brand")
            card_last4 = card.get("last4")

        # Mark payment as PAID
        payment = order.payments.get(stripe_payment_intent=intent["id"])
        
        payment.card_brand = card_brand
        payment.card_last4 = card_last4
        payment.payment_status = Payment.Status.SUCCESS
        payment.save()

        # Mark order as PAID
        order.status = Order.Status.PENDING
        order.save()

        return order
    except Exception as e:
        logger.exception("Failed to handle payment intent succeeded: %s", e)
        raise