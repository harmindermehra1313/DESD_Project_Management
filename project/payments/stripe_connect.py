import stripe
from django.conf import settings
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

# Create connected account for producer
def create_connected_account(producer):
    if producer.stripe_account_id:
        return producer.stripe_account_id

    account = stripe.Account.create(
        type="express",
        country="GB",
        email=producer.contact_email,
        capabilities={
            "transfers": {"requested": True},
        },
        business_type="individual",
    )

    producer.stripe_account_id = account.id
    producer.save(update_fields=["stripe_account_id"])

    return account.id


# Create onboarding link
def create_onboarding_link(producer):
    if not producer.stripe_account_id:
        create_connected_account(producer)

    return stripe.AccountLink.create(
        account=producer.stripe_account_id,
        refresh_url=settings.STRIPE_ONBOARDING_REFRESH_URL,
        return_url=settings.STRIPE_ONBOARDING_RETURN_URL,
        type="account_onboarding",
    ).url


# Retrieve connected account status
def get_account_status(producer):
    if not producer.stripe_account_id:
        return None

    return stripe.Account.retrieve(producer.stripe_account_id)


# Create transfer (weekly payout)
def create_transfer(settlement):
    producer = settlement.producer

    if not producer.stripe_account_id:
        raise ValueError("Producer does not have a Stripe connected account.")

    amount_pence = int(settlement.payout_amount * Decimal("100"))

    transfer = stripe.Transfer.create(
        amount=amount_pence,
        currency="gbp",
        destination=producer.stripe_account_id,
        description=f"Weekly payout for {settlement.settlement_week}",
    )

    return transfer
