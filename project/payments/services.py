from decimal import Decimal
from django.conf import settings
from .stripe_client import get_stripe
from django.core.exceptions import ValidationError

stripe = get_stripe()

MIN_ORDER = Decimal("1.00")

def create_payment_intent(amount, session_key=None, user_id=None):
    if amount < MIN_ORDER:
        raise ValidationError("Minimum order amount is £1.00")
    
    # return stripe.PaymentIntent.create(
    #     amount=int(order.final_total_price * 100),
    #     currency="gbp",
    #     payment_method_types=["card"],
    #     metadata={"order_id": order.id},
    #     setup_future_usage=None,
    # )
    return stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="gbp",
            payment_method_types=["card"],
            metadata={
                "session_key": session_key or "",
                "user_id": user_id or "",
            },
            setup_future_usage=None,
        )

def create_transfer(producer, amount, order):
    return stripe.Transfer.create(
        amount=int(amount * 100),
        currency="gbp",
        destination=producer.stripe_account_id,
        transfer_group=f"order_{order.id}",
    )