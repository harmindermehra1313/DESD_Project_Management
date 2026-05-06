from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from BRFN.decorators import producer_required
from django.contrib import messages
from accounts.serializers.producer_payout import ProducerPayoutSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from payments.stripe_connect import (
    create_connected_account,
    create_onboarding_link,
    get_account_status,
)

STRIPE_REQUIREMENT_MESSAGES = {
    "business_profile.url": "Business website or social media link is required.",
    "business_profile.mcc": "Business category must be selected.",
    "individual.address.line1": "Home address line 1 is required.",
    "individual.address.city": "City is required.",
    "individual.address.postal_code": "Postal code is required.",
    "individual.dob.day": "Date of birth (day) is required.",
    "individual.dob.month": "Date of birth (month) is required.",
    "individual.dob.year": "Date of birth (year) is required.",
    "individual.email": "Email address is required.",
    "individual.first_name": "First name is required.",
    "individual.last_name": "Last name is required.",
    "individual.phone": "Phone number is required.",
    "external_account": "Bank account details are required.",
}

# Producer Stripe dashboard (main page)

@login_required
@producer_required
def stripe_dashboard(request):
    producer = request.user.producer_profile
    account = get_account_status(producer)

    requirements = []
    if account and hasattr(account, "requirements") and account.requirements:
        for item in account.requirements.currently_due:
            requirements.append(STRIPE_REQUIREMENT_MESSAGES.get(item, item))

    context = {
        "producer": producer,
        "account": account,
        "has_stripe": bool(producer.stripe_account_id),
        "payouts_enabled": getattr(account, "payouts_enabled", False) if account else False,
        "charges_enabled": getattr(account, "charges_enabled", False) if account else False,
        "requirements": requirements,
    }

    return render(request, "accounts/stripe_dashboard.html", context)


# Start Stripe onboarding (connect account)

@login_required
@producer_required
def connect_stripe_account(request):
    producer = request.user.producer_profile

    # Create account if missing
    create_connected_account(producer)

    # Generate onboarding link
    onboarding_url = create_onboarding_link(producer)

    return redirect(onboarding_url)


# Onboarding refresh (user closed window)

@login_required
@producer_required
def onboarding_refresh(request):
    producer = request.user.producer_profile

    onboarding_url = create_onboarding_link(producer)
    return redirect(onboarding_url)

@login_required
@producer_required
def update_payout_method(request):
    if request.method == "POST":
        method = request.POST.get("payout_method")
        producer = request.user.producer_profile

        # Prevent selecting Stripe if not fully enabled
        account = get_account_status(producer)
        if method == "STRIPE" and not (account and account.payouts_enabled):
            messages.error(request, "Stripe payouts are not fully enabled yet.")
            return redirect("accounts:producer_stripe_dashboard")

        producer.payout_method = method
        producer.save(update_fields=["payout_method"])

        messages.success(request, "Payout method updated.")
        return redirect("accounts:producer_stripe_dashboard")

@login_required
@producer_required
def producer_settings(request):
    producer = request.user.producer_profile
    serializer = ProducerPayoutSerializer(producer)

    return render(request, "accounts/producer_settings.html", {
        "producer": producer,
        "serializer": serializer,
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_payout_api(request):
    producer = request.user.producer_profile
    serializer = ProducerPayoutSerializer(producer, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response({"success": True, "message": "Payout details updated."})

    return Response({"success": False, "errors": serializer.errors}, status=400)
